/**
 * Dashboard application logic.
 * Handles data loading, rendering, and theme management.
 */

// ---- Theme ----

function toggleTheme() {
    const html = document.documentElement;
    const current = html.getAttribute('data-theme');
    const next = current === 'dark' ? 'light' : 'dark';
    html.setAttribute('data-theme', next);
    localStorage.setItem('theme', next);
    document.getElementById('theme-icon').textContent = next === 'dark' ? '\u263E' : '\u2600';
}

// Apply saved theme
(function () {
    const saved = localStorage.getItem('theme') || 'dark';
    document.documentElement.setAttribute('data-theme', saved);
    const icon = document.getElementById('theme-icon');
    if (icon) icon.textContent = saved === 'dark' ? '\u263E' : '\u2600';
})();

// ---- Utilities ----

function escapeHtml(text) {
    const div = document.createElement('div');
    div.textContent = text || '';
    return div.innerHTML;
}

function seoClass(score) {
    if (score >= 80) return 'seo-high';
    if (score >= 60) return 'seo-mid';
    return 'seo-low';
}

function timeAgo(dateStr) {
    if (!dateStr) return 'Unknown';
    const date = new Date(dateStr);
    const now = new Date();
    const diffDays = Math.floor((now - date) / (1000 * 60 * 60 * 24));
    if (diffDays === 0) return 'Today';
    if (diffDays === 1) return 'Yesterday';
    if (diffDays < 7) return `${diffDays} days ago`;
    return dateStr;
}

// ---- Dashboard (index.html) ----

async function loadDashboard() {
    // Only run on index page
    if (!document.getElementById('total-posts')) return;

    // Load stats
    try {
        const statsResp = await fetch('data/stats.json');
        const stats = await statsResp.json();

        document.getElementById('total-posts').textContent = stats.total_posts || 0;
        document.getElementById('avg-seo').textContent = stats.avg_seo_score ? `${stats.avg_seo_score}/100` : '-';
        document.getElementById('avg-words').textContent = stats.avg_word_count ? stats.avg_word_count.toLocaleString() : '-';
        document.getElementById('last-generated').textContent = timeAgo(stats.last_generated);
    } catch (e) {
        console.warn('Could not load stats:', e);
    }

    // Load posts
    try {
        const postsResp = await fetch('data/posts.json');
        const posts = await postsResp.json();

        // Today's draft
        const todayEl = document.getElementById('today-draft');
        if (posts.length > 0) {
            const latest = posts[0];
            todayEl.innerHTML = `
                <div class="draft-preview">
                    <h3>${escapeHtml(latest.title)}</h3>
                    <div class="draft-meta">
                        <span>${latest.date}</span>
                        <span>${latest.word_count.toLocaleString()} words</span>
                        <span class="seo-badge ${seoClass(latest.seo_score)}">SEO: ${latest.seo_score}</span>
                        <span class="status-badge status-${latest.status}">${latest.status}</span>
                    </div>
                    <div class="draft-keywords">
                        ${(latest.keywords || []).map(k => `<span class="tag">${escapeHtml(k)}</span>`).join(' ')}
                    </div>
                    <a href="post.html?file=${encodeURIComponent(latest.filename)}" class="btn btn-primary">Read Full Post</a>
                </div>
            `;
        } else {
            todayEl.innerHTML = '<p class="muted">No drafts yet. Generate your first blog post!</p>';
        }

        // Recent posts
        const recentEl = document.getElementById('recent-posts');
        const recentPosts = posts.slice(1, 8); // Skip the first (shown above)
        if (recentPosts.length > 0) {
            recentEl.innerHTML = recentPosts.map(p => `
                <a href="post.html?file=${encodeURIComponent(p.filename)}" class="post-card">
                    <div class="post-card-date">${p.date}</div>
                    <div class="post-card-title">${escapeHtml(p.title)}</div>
                    <div class="post-card-meta">
                        <span>${p.word_count.toLocaleString()} words</span>
                        <span class="seo-badge ${seoClass(p.seo_score)}">${p.seo_score}</span>
                    </div>
                </a>
            `).join('');
        } else {
            recentEl.innerHTML = '<p class="muted">No additional posts yet.</p>';
        }
    } catch (e) {
        document.getElementById('today-draft').innerHTML =
            '<p class="muted">No data available. Run the pipeline to generate your first post.</p>';
        document.getElementById('recent-posts').innerHTML = '';
    }
}

// Auto-load dashboard on page load
document.addEventListener('DOMContentLoaded', loadDashboard);
