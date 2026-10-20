// Images pasted or dropped into the notes (or picked with the file input) are
// uploaded straight away and inserted as markdown at the cursor.
const form = document.getElementById("notes-form");
const text = document.getElementById("notes-text");

async function upload(file) {
  const body = new FormData();
  body.append("book", form.dataset.book);
  body.append("file", file);
  const res = await fetch("/api/notes/images", { method: "POST", body });
  if (!res.ok) return alert("That image couldn't be added.");
  const { url } = await res.json();
  const at = text.selectionStart;
  text.setRangeText(`\n![](${url})\n`, at, text.selectionEnd, "end");
  text.focus();
}

const images = (list) => [...(list ?? [])].filter((f) => f.type.startsWith("image/"));
text.addEventListener("paste", (e) => {
  const files = images(e.clipboardData?.files);
  if (files.length) { e.preventDefault(); files.forEach(upload); }
});
text.addEventListener("drop", (e) => {
  const files = images(e.dataTransfer?.files);
  if (files.length) { e.preventDefault(); files.forEach(upload); }
});
document.getElementById("notes-image").addEventListener("change", (e) => images(e.target.files).forEach(upload));
