from pytest_bdd import parsers, scenarios, then

scenarios("statistics.feature")


@then(parsers.parse('"{first}" comes before "{second}"'))
def order(ctx, first, second):
    assert ctx["response"].text.index(first) < ctx["response"].text.index(second)
