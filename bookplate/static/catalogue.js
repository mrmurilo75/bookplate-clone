// Add-book catalogue search: Open Library results through /api/booksearch;
// picking one fills the form and asks the server to fetch its cover on save.
const q = document.getElementById("cat-q");
const results = document.getElementById("cat-results");
const set = (id, value) => { if (value != null) document.getElementById(id).value = value; };

async function search() {
  if (!q.value.trim()) return;
  results.innerHTML = "<li class='muted'>Searching…</li>";
  try {
    const res = await fetch("/api/booksearch?q=" + encodeURIComponent(q.value.trim()));
    if (!res.ok) throw new Error(res.status);
    const { results: books = [] } = await res.json();
    results.innerHTML = books.length ? "" : "<li class='muted'>Nothing found. Enter the book by hand below.</li>";
    for (const b of books) {
      const li = document.createElement("li");
      const btn = document.createElement("button");
      btn.type = "button";
      btn.className = "cat-result";
      if (b.coverId) {
        const img = document.createElement("img");
        img.src = `/api/booksearch/cover?id=${b.coverId}`;
        img.alt = "";
        btn.append(img);
      }
      const text = document.createElement("span");
      text.textContent = `${b.title} — ${b.author}${b.year ? ` (${b.year})` : ""}`;
      btn.append(text);
      btn.onclick = () => {
        set("f-title", b.title);
        set("f-author", b.author);
        set("f-pages", b.pages);
        set("f-work", b.workId ?? "");
        set("f-cover-id", b.coverId ?? "");
        document.getElementById("cat-cover-note").hidden = !b.coverId;
        results.innerHTML = "";
        document.getElementById("f-title").focus();
      };
      li.append(btn);
      results.append(li);
    }
  } catch {
    results.innerHTML = "<li class='error'>Search failed. Enter the book by hand below.</li>";
  }
}

document.getElementById("cat-go")?.addEventListener("click", search);
q?.addEventListener("keydown", (e) => { if (e.key === "Enter") { e.preventDefault(); search(); } });
