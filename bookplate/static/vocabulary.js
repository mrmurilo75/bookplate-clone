// Looks a word up in Wiktionary (through /api/define); picking a sense fills
// the form, or the reader writes their own definition.
const word = document.getElementById("w-word");
const senses = document.getElementById("w-senses");
const fill = (id, v) => (document.getElementById(id).value = v ?? "");

async function lookup() {
  if (!word.value.trim()) return;
  senses.textContent = "Looking up…";
  try {
    const res = await fetch("/api/define?word=" + encodeURIComponent(word.value.trim()));
    if (!res.ok) throw new Error(res.status);
    const { entry } = await res.json();
    senses.innerHTML = "";
    if (!entry || !entry.senses.length) {
      senses.textContent = "No dictionary entry. Write your own definition below.";
      return;
    }
    word.value = entry.word;
    for (const s of entry.senses) {
      const btn = document.createElement("button");
      btn.type = "button";
      btn.className = "sense";
      btn.innerHTML = "<em></em> <span></span>";
      btn.querySelector("em").textContent = s.partOfSpeech;
      btn.querySelector("span").textContent = s.definition;
      btn.onclick = () => {
        fill("w-pos", s.partOfSpeech);
        fill("w-def", s.definition);
        fill("w-ex", s.example);
        senses.querySelectorAll(".sense").forEach((b) => b.classList.toggle("active", b === btn));
      };
      senses.append(btn);
    }
  } catch {
    senses.textContent = "Lookup failed. Write your own definition below.";
  }
}

document.getElementById("w-lookup").addEventListener("click", lookup);
word.addEventListener("keydown", (e) => { if (e.key === "Enter") { e.preventDefault(); lookup(); } });
