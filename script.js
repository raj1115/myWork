document.addEventListener("DOMContentLoaded", () => {
  const refineToggle = document.getElementById("refine-toggle");
  const extraQs      = document.getElementById("extra-questions");
  const form         = document.getElementById("recommendation-form");
  const submitBtn    = form.querySelector("button[type=submit]");
  const resultsDiv   = document.getElementById("results");
  const initList     = document.getElementById("initial-list");
  const refinedCard  = document.getElementById("refined-results");
  const refinedList  = document.getElementById("refined-list");

  refineToggle.addEventListener("change", () => {
    extraQs.classList.toggle("d-none", !refineToggle.checked);
  });

  form.addEventListener("submit", async (e) => {
    e.preventDefault();
    // disable + show spinner
    submitBtn.disabled = true;
    submitBtn.innerHTML = `<span class="spinner-border spinner-border-sm me-2" role="status"></span>Loading...`;

    try {
      // build basic profile
      const basic = {
        high_bp:       document.querySelector('input[name="high_bp"]:checked').value === "yes",
        weight_loss:   document.querySelector('input[name="weight_loss"]:checked').value === "yes",
        pregnant:      document.querySelector('input[name="pregnant"]:checked').value === "yes",
        child:         document.querySelector('input[name="child"]:checked').value === "yes",
        diet:          document.getElementById("diet").value,
        allergy:       document.getElementById("allergy").value,
      };

      let main_goal = document.getElementById("main_goal").value || undefined;
      let top_n     = Math.min(10, Math.max(2, +document.getElementById("top_n").value));

      let extra = null;
      if (refineToggle.checked) {
        extra = {
          activity:  document.getElementById("activity").value,
          spicy:     document.getElementById("spicy").value,
          macro:     document.getElementById("macro").value,
          cook_time: document.getElementById("cook_time").value,
          budget:    document.getElementById("budget").checked,
        };
      }

      const payload = { basic_profile: basic, top_n };
      if (main_goal)   payload.main_goal   = main_goal;
      if (extra)       payload.extra_profile = extra;

      const res = await fetch("/recommend", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(payload),
      });
      if (!res.ok) throw new Error(`Server error (${res.status})`);
      const data = await res.json();

      // show initial
      initList.innerHTML = "";
      data.initial.forEach(dish => {
        const li = document.createElement("li");
        li.className = "list-group-item";
        li.textContent = dish;
        initList.appendChild(li);
      });

      // show refined if any
      if (data.refined) {
        refinedList.innerHTML = "";
        data.refined.forEach(dish => {
          const li = document.createElement("li");
          li.className = "list-group-item";
          li.textContent = dish;
          refinedList.appendChild(li);
        });
        refinedCard.classList.remove("d-none");
      } else {
        refinedCard.classList.add("d-none");
      }

      resultsDiv.classList.remove("d-none");
      resultsDiv.scrollIntoView({ behavior: "smooth" });

    } catch (err) {
      console.error(err);
      alert("Oops! Something went wrong. Please try again.");
    } finally {
      // restore button
      submitBtn.disabled = false;
      submitBtn.textContent = "Get Recommendations";
    }
  });
});