/**
 * SpinCoach AI - Table Tennis Coaching Logic
 * Vanilla JavaScript implementation for bandit-based drill recommendations.
 */

const state = {
    isLoading: false,
    currentRunId: null,
    stats: {
        events: 0,
        avg_reward: 0
    }
};

// DOM Elements
const elements = {
    form: document.getElementById('recommendation-form'),
    queryInput: document.getElementById('query'),
    skillSelect: document.getElementById('skill'),
    goalSelect: document.getElementById('goal'),
    submitBtn: document.getElementById('submit-btn'),
    
    searchView: document.getElementById('search-view'),
    historyView: document.getElementById('history-view'),
    resultsView: document.getElementById('results-view'),
    backBtn: document.getElementById('back-btn'),
    viewHistoryBtn: document.getElementById('view-history-btn'),
    historyBackBtn: document.getElementById('history-back-btn'),
    
    chosenCard: document.getElementById('chosen-card'),
    drillTitle: document.getElementById('drill-title'),
    decisionScope: document.getElementById('decision-scope'),
    totalPulls: document.getElementById('total-pulls'),
    
    candidatesList: document.getElementById('candidates-list'),
    
    feedbackArea: document.getElementById('feedback-area'),
    ratingButtons: document.querySelectorAll('.rating-btn'),
    
    historyList: document.getElementById('history-list'),
    learningSummary: document.getElementById('learning-summary'),
    histEvents: document.getElementById('hist-events'),
    histReward: document.getElementById('hist-reward'),
    histExploration: document.getElementById('hist-exploration'),
    
    statsEvents: document.getElementById('stats-events'),
    statsReward: document.getElementById('stats-reward'),
    
    statusMessage: document.getElementById('status-message')
};

/**
 * Show a temporary status message
 */
function showStatus(text, type = 'success') {
    elements.statusMessage.textContent = text;
    elements.statusMessage.className = `status-${type}`;
    elements.statusMessage.style.display = 'block';
    
    setTimeout(() => {
        elements.statusMessage.style.display = 'none';
    }, 3000);
}

/**
 * Update the UI based on loading state
 */
function setLoading(loading) {
    state.isLoading = loading;
    elements.submitBtn.disabled = loading;
    const btnText = elements.submitBtn.querySelector('.btn-text');
    const loader = elements.submitBtn.querySelector('.loader');
    
    if (loading) {
        btnText.textContent = 'Analyzing...';
        loader.classList.remove('hidden');
    } else {
        btnText.textContent = 'Get Recommendation';
        loader.classList.add('hidden');
    }
}

/**
 * Handle Recommendation Request
 */
async function getRecommendation(e) {
    e.preventDefault();
    if (state.isLoading) return;

    const payload = {
        query: elements.queryInput.value,
        skill: elements.skillSelect.value,
        goal: elements.goalSelect.value
    };

    setLoading(true);
    
    try {
        const response = await fetch('/api/recommend', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify(payload)
        });

        if (!response.ok) throw new Error('Failed to fetch recommendation');

        const data = await response.json();
        renderRecommendation(data);
        loadHistory(); // Refresh history after new recommendation
        showStatus('Boom! Found the perfect drill for you! 🎯', 'success');
    } catch (error) {
        console.error(error);
        showStatus('Oops! Something went wrong. Let\'s try again! 😅', 'error');
    } finally {
        setLoading(false);
    }
}

/**
 * Render the recommendation result
 */
function renderRecommendation(data) {
    state.currentRunId = data.run_id;
    
    // Switch views
    elements.searchView.classList.add('hidden');
    elements.resultsView.classList.remove('hidden');
    
    // Chosen Drill
    elements.drillTitle.textContent = data.chosen.title;
    elements.decisionScope.textContent = data.decision_scope;
    elements.totalPulls.textContent = data.context_total_pulls;
    
    // Candidates
    elements.candidatesList.innerHTML = '';
    data.candidates.forEach(cand => {
        const item = document.createElement('div');
        item.className = 'candidate-item';
        item.innerHTML = `
            <div class="candidate-info">
                <div class="candidate-name">${cand.title}</div>
                <div class="candidate-score">Score: ${cand.score.toFixed(4)}</div>
            </div>
            ${cand.id === data.chosen_id ? '<span class="badge badge-scope" style="margin:0">Chosen</span>' : ''}
        `;
        elements.candidatesList.appendChild(item);
    });

    // Reset feedback buttons
    elements.ratingButtons.forEach(btn => btn.classList.remove('active'));
    
    // Scroll to result
    elements.resultsView.scrollIntoView({ behavior: 'smooth', block: 'start' });
}

/**
 * Handle Feedback Submission
 */
async function submitFeedback(rating) {
    if (!state.currentRunId) return;

    try {
        const response = await fetch('/api/feedback', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({
                run_id: state.currentRunId,
                rating: parseInt(rating)
            })
        });

        if (!response.ok) throw new Error('Failed to submit feedback');

        const data = await response.json();
        updateStats(data.stats);
        loadHistory(); // Refresh history after feedback
        showStatus('Awesome! SpinCoach is getting smarter! 🧠✨', 'success');
        
        // Visual feedback on button
        elements.ratingButtons.forEach(btn => {
            if (btn.dataset.rating == rating) {
                btn.classList.add('active');
            } else {
                btn.classList.remove('active');
            }
        });

    } catch (error) {
        console.error(error);
        showStatus('Error saving feedback.', 'error');
    }
}

/**
 * Update Stats Display
 */
function updateStats(stats) {
    state.stats = stats;
    elements.statsEvents.textContent = stats.events;
    elements.statsReward.textContent = stats.avg_reward.toFixed(2);
    
    // Also update history stats if visible
    if (elements.histEvents) elements.histEvents.textContent = stats.events;
    if (elements.histReward) elements.histReward.textContent = stats.avg_reward.toFixed(2);
    
    // Animate values slightly
    elements.statsEvents.style.transform = 'scale(1.2)';
    setTimeout(() => elements.statsEvents.style.transform = 'scale(1)', 200);
}

/**
 * Load and Render History
 */
async function loadHistory() {
    try {
        const response = await fetch('/api/history');
        if (!response.ok) throw new Error('Failed to fetch history');
        
        const data = await response.json();
        renderHistory(data);
    } catch (error) {
        console.error('Error loading history:', error);
    }
}

/**
 * Render History List and Summary
 */
function renderHistory(data) {
    const { events, summary } = data;
    
    // Update Stats
    updateStats({
        events: summary.events,
        avg_reward: summary.avg_reward,
        recent_avg_reward: summary.recent_avg_reward
    });

    elements.histEvents.textContent = summary.events;
    elements.histReward.textContent = summary.avg_reward.toFixed(2);
    elements.histExploration.textContent = `${summary.global_count}/${summary.context_count}`;
    
    // Update Learning Summary Message
    if (summary.events === 0) {
        elements.learningSummary.textContent = "System is currently exploring and learning from your feedback...";
    } else if (summary.events < 5) {
        elements.learningSummary.textContent = "Gathering initial data. Keep training to help SpinCoach specialize!";
    } else {
        const trend = summary.recent_avg_reward > summary.avg_reward ? "improving" : "stabilizing";
        elements.learningSummary.textContent = `SpinCoach is ${trend} based on ${summary.events} sessions. Learning from your ${summary.context_count} contextual choices.`;
    }

    // Update List
    if (events.length === 0) {
        elements.historyList.innerHTML = '<div class="empty-history">No training history yet. Start your first drill!</div>';
        return;
    }

    elements.historyList.innerHTML = events.map(event => `
        <div class="history-item">
            <div class="history-info">
                <div class="history-title">${event.chosen_title}</div>
                <div class="history-meta">
                    ${event.context.skill} • ${event.context.goal} • ${event.decision_scope}
                </div>
            </div>
            <div class="history-reward" style="color: ${getRewardColor(event.reward)}">
                ${formatHistoryReward(event.reward)}
            </div>
        </div>
    `).join('');
}

function formatHistoryReward(reward) {
    const rating = Math.round(reward * 4) + 1;
    return `${rating} ⭐`;
}

function getRewardColor(reward) {
    if (reward <= 0.25) return 'var(--color-text-muted)';
    if (reward >= 0.8) return '#27ae60';
    if (reward >= 0.6) return '#f39c12';
    return 'var(--color-primary)';
}

// Event Listeners
elements.form.addEventListener('submit', getRecommendation);

elements.backBtn.addEventListener('click', () => {
    elements.resultsView.classList.add('hidden');
    elements.searchView.classList.remove('hidden');
});

elements.viewHistoryBtn.addEventListener('click', () => {
    elements.searchView.classList.add('hidden');
    elements.historyView.classList.remove('hidden');
    loadHistory();
});

elements.historyBackBtn.addEventListener('click', () => {
    elements.historyView.classList.add('hidden');
    elements.searchView.classList.remove('hidden');
});

elements.ratingButtons.forEach(btn => {
    btn.addEventListener('click', () => {
        submitFeedback(btn.dataset.rating);
    });
});

// Initial state
window.addEventListener('DOMContentLoaded', () => {
    const introOverlay = document.getElementById('intro-overlay');
    
    // Start the reveal animation after 6 seconds
    setTimeout(() => {
        if (introOverlay) {
            introOverlay.classList.add('reveal');
            
            // Remove the overlay from DOM after the curtain transition (approx 1s)
            setTimeout(() => {
                introOverlay.style.display = 'none';
            }, 1000);
        }
    }, 6000);
});

loadHistory();
console.log('SpinCoach AI UI Initialized');
