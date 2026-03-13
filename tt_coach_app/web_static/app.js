const form = document.querySelector("#recommend-form");
const statsEl = document.querySelector("#stats");
const resultPanel = document.querySelector("#result-panel");
const chosenTitle = document.querySelector("#chosen-title");
const chosenMeta = document.querySelector("#chosen-meta");
const scopeBadge = document.querySelector("#scope-badge");
const candidateList = document.querySelector("#candidate-list");
const feedbackStatus = document.querySelector("#feedback-status");
const ratingButtons = Array.from(document.querySelectorAll(".rating"));

let activeRunId = null;

async function fetchStats() {
  const response = await fetch("/api/stats");
  const stats = await response.json();
  if (!stats.events) {
    statsEl.textContent = "No feedback logged yet";
    return;
  }

  statsEl.textContent = `${stats.events} events, avg reward ${stats.avg_reward}, last 10 avg ${stats.recent_avg_reward}`;
}

function renderCandidates(candidates, chosenId) {
  candidateList.innerHTML = "";
  candidates.forEach((candidate, index) => {
    const item = document.createElement("li");
    if (candidate.id === chosenId) {
      item.classList.add("chosen");
    }

    item.innerHTML = `
      <span class="candidate-title">${index + 1}. ${candidate.title}</span>
      <span class="candidate-meta">${candidate.id} • score ${candidate.score.toFixed(3)}${candidate.id === chosenId ? " • chosen" : ""}</span>
    `;
    candidateList.appendChild(item);
  });
}

function resetRatings() {
  ratingButtons.forEach((button) => button.classList.remove("active"));
}

form.addEventListener("submit", async (event) => {
  event.preventDefault();
  resetRatings();
  feedbackStatus.textContent = "Finding a recommendation...";

  const payload = {
    query: document.querySelector("#query").value,
    skill: document.querySelector("#skill").value,
    goal: document.querySelector("#goal").value,
  };

  const response = await fetch("/api/recommend", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(payload),
  });
  const data = await response.json();

  if (!response.ok) {
    feedbackStatus.textContent = data.detail ? `${data.error} ${data.detail}` : (data.error || "Could not get a recommendation.");
    return;
  }

  activeRunId = data.run_id;
  resultPanel.classList.remove("hidden");
  chosenTitle.textContent = data.chosen?.title || data.chosen_id;
  chosenMeta.textContent = `${data.query} • ${data.context.skill} / ${data.context.goal} • ctx pulls ${data.context_total_pulls}`;
  scopeBadge.textContent = `${data.decision_scope} scope`;
  renderCandidates(data.candidates, data.chosen_id);
  feedbackStatus.textContent = "Rate the chosen drill to update the model.";
});

ratingButtons.forEach((button) => {
  button.addEventListener("click", async () => {
    if (!activeRunId) {
      feedbackStatus.textContent = "Get a recommendation first.";
      return;
    }

    resetRatings();
    button.classList.add("active");
    feedbackStatus.textContent = "Saving feedback...";

    const response = await fetch("/api/feedback", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ run_id: activeRunId, rating: Number(button.dataset.rating) }),
    });
    const data = await response.json();

    if (!response.ok) {
      feedbackStatus.textContent = data.detail ? `${data.error} ${data.detail}` : (data.error || "Could not save feedback.");
      return;
    }

    activeRunId = null;
    feedbackStatus.textContent = `Saved rating ${button.dataset.rating}. Reward ${data.reward.toFixed(2)} recorded for ${data.chosen_id}.`;
    await fetchStats();
  });
});

fetchStats().catch(() => {
  statsEl.textContent = "Stats unavailable";
});
