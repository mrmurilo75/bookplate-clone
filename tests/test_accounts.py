from conftest import jpeg, new_client
from pytest_bdd import given, parsers, scenarios, then, when
from sqlmodel import Session, SQLModel, func, select

from bookplate import storage
from bookplate.db import engine

scenarios("accounts.feature")


@given("a new Bookplate")
def new_bookplate():
    pass


@given("registration is open")
def registration_open(open_registration):
    pass


@given(parsers.parse('"{name}" is also signed in on a second device'))
def second_device(ctx, name):
    client = new_client()
    client.post("/login", data={"email": f"{name.lower()}@example.com", "password": "password123"})
    ctx["second"] = client


@when(parsers.parse('a visitor opens "{path}"'))
@when(parsers.parse('a visitor calls "{path}"'))
def visitor_opens(ctx, path):
    ctx["readers"]["visitor"] = new_client()
    ctx["current"] = "visitor"
    ctx["response"] = ctx["readers"]["visitor"].get(path)


@when(parsers.parse('a visitor tries to sign up as "{name}"'))
def visitor_signs_up(ctx, name):
    ctx["response"] = new_client().post(
        "/signup", data={"name": name, "email": f"{name.lower()}@example.com", "password": "password123"}
    )


@when(parsers.parse('a visitor signs in as "{email}" with "{password}"'))
def visitor_signs_in(ctx, email, password):
    ctx["readers"]["visitor"] = new_client()
    ctx["current"] = "visitor"
    ctx["response"] = ctx["readers"]["visitor"].post("/login", data={"email": email, "password": password})


@when("they sign out")
def sign_out(ctx):
    ctx["response"] = ctx["readers"][ctx["current"]].post("/logout")


@when(parsers.parse('"{name}" changes the password from "{old}" to "{new}"'))
def change_password(ctx, name, old, new):
    res = ctx["readers"][name].post("/settings/password", data={"current": old, "new": new})
    assert "Password changed" in res.text


@then("the second device is signed out")
def second_signed_out(ctx):
    assert ctx["second"].get("/api/books").status_code == 401


@then(parsers.parse('"{name}" can sign in with "{password}"'))
def can_sign_in(ctx, name, password):
    res = new_client().post("/login", data={"email": f"{name.lower()}@example.com", "password": password})
    assert res.url.path == "/"


@when(parsers.parse('"{name}" deletes the account with "{password}"'))
def delete_account(ctx, name, password):
    client = ctx["readers"][name]
    book = client.get("/api/books").json()["books"][0]
    client.post("/api/covers", data={"id": book["id"]}, files={"file": ("c.jpg", jpeg(60, 90), "image/jpeg")})
    ctx["response"] = client.post("/settings/delete", data={"password": password})


@then(parsers.parse('no rows or images of "{name}" are left'))
def nothing_left(ctx, name):
    with Session(engine) as db:
        for table in SQLModel.metadata.sorted_tables:
            if table.name != "alembic_version":
                assert db.exec(select(func.count()).select_from(table)).one() == 0, table.name
    assert not any(p.is_file() for p in storage.config.uploads_dir.rglob("*"))
