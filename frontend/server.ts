import express from 'express';
import path from 'path';
import { fileURLToPath } from 'url';

const __filename = fileURLToPath(import.meta.url);
const __dirname = path.dirname(__filename);

const app = express();
const PORT = 3000;

app.use(express.json());
app.use(express.static(path.join(__dirname, '.')));

// In-memory store for session history
const history: any[] = [];
const stats = {
    events: 0,
    avg_reward: 0,
    global_count: 0,
    context_count: 0
};

// Mock API for Recommendation
app.post('/api/recommend', (req, res) => {
    const { query, skill, goal } = req.body;
    
    // Simulate some logic
    const drills = [
        { id: 'd1', title: 'Forehand Topspin Multiball', score: 0.95 },
        { id: 'd2', title: 'Backhand Push to Corner', score: 0.88 },
        { id: 'd3', title: 'Footwork: 2-Point Side-to-Side', score: 0.82 },
        { id: 'd4', title: 'Service: Short Pendulum with Backspin', score: 0.79 },
        { id: 'd5', title: 'Receive: Flick against Short Serve', score: 0.75 }
    ];

    // Filter or sort based on goal (mocking)
    const filtered = drills.filter(d => d.title.toLowerCase().includes(goal.toLowerCase()) || Math.random() > 0.5);
    const chosen = filtered[0] || drills[0];
    const decision_scope = Math.random() > 0.5 ? 'context' : 'global';

    const run_id = 'run_' + Math.random().toString(36).substr(2, 9);
    
    // Pre-record the event (reward will be updated later)
    history.unshift({
        run_id,
        query,
        chosen_id: chosen.id,
        chosen_title: chosen.title,
        reward: 0,
        decision_scope,
        context: { skill, goal },
        timestamp: new Date().toISOString()
    });

    if (decision_scope === 'global') stats.global_count++;
    else stats.context_count++;

    setTimeout(() => {
        res.json({
            run_id,
            query: query,
            context: { skill, goal },
            decision_scope,
            context_total_pulls: Math.floor(Math.random() * 100),
            chosen_id: chosen.id,
            chosen: chosen,
            candidates: filtered.slice(0, 5)
        });
    }, 800); // Simulate network delay
});

// Mock API for Feedback
app.post('/api/feedback', (req, res) => {
    const { run_id, rating } = req.body;
    const reward = rating / 5;

    // Update history
    const event = history.find(e => e.run_id === run_id);
    if (event) {
        event.reward = reward;
    }

    stats.events++;
    stats.avg_reward = (stats.avg_reward * (stats.events - 1) + reward) / stats.events;
    
    setTimeout(() => {
        res.json({
            ok: true,
            chosen_id: event?.chosen_id || 'd1',
            reward: reward,
            stats: {
                events: stats.events,
                avg_reward: stats.avg_reward,
                recent_avg_reward: stats.avg_reward * 1.1 // Mocking a slight improvement
            }
        });
    }, 500);
});

// Mock API for History
app.get('/api/history', (req, res) => {
    res.json({
        events: history.slice(0, 10), // Return last 10 events
        summary: {
            events: stats.events,
            avg_reward: stats.avg_reward,
            recent_avg_reward: stats.avg_reward * 1.1,
            global_count: stats.global_count,
            context_count: stats.context_count
        }
    });
});

app.listen(PORT, '0.0.0.0', () => {
    console.log(`SpinCoach AI Mock Server running on http://localhost:${PORT}`);
});
