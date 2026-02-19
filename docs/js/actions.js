/**
 * GitHub Actions API integration.
 * All API calls use the PAT stored in localStorage (client-side only).
 */

const REPO = 'Abivarma/blog-automation';

function getToken() {
    return localStorage.getItem('gh_pat');
}

function ghHeaders() {
    const token = getToken();
    if (!token) return null;
    return {
        'Authorization': `token ${token}`,
        'Accept': 'application/vnd.github.v3+json',
        'Content-Type': 'application/json',
    };
}

/**
 * Trigger a workflow_dispatch event.
 */
async function dispatchWorkflow(workflowFile, inputs = {}) {
    const headers = ghHeaders();
    if (!headers) {
        showStatus('Please configure your GitHub token in Settings first.', 'warning');
        return false;
    }

    try {
        const resp = await fetch(
            `https://api.github.com/repos/${REPO}/actions/workflows/${workflowFile}/dispatches`,
            {
                method: 'POST',
                headers,
                body: JSON.stringify({ ref: 'main', inputs }),
            }
        );

        if (resp.status === 204) {
            return true;
        }

        const data = await resp.json().catch(() => ({}));
        console.error('Dispatch failed:', resp.status, data);
        return false;
    } catch (e) {
        console.error('Dispatch error:', e);
        return false;
    }
}

/**
 * Trigger daily blog generation.
 */
async function triggerGeneration() {
    showStatus('Triggering blog generation...', 'info');
    const ok = await dispatchWorkflow('daily-blog-generator.yml');
    showStatus(
        ok ? 'Blog generation triggered! Check GitHub Actions for progress.' : 'Failed to trigger. Check your GitHub token.',
        ok ? 'success' : 'error'
    );
}

/**
 * Trigger with a specific backup topic.
 */
async function switchTopic() {
    const index = document.getElementById('topic-select').value;
    showStatus(`Switching to backup topic #${index}...`, 'info');
    const ok = await dispatchWorkflow('daily-blog-generator.yml', { topic_index: index });
    showStatus(
        ok ? `Topic switch triggered (topic #${index})! Check GitHub Actions.` : 'Failed to trigger. Check your GitHub token.',
        ok ? 'success' : 'error'
    );
}

/**
 * Trigger dry run (no GPT-4, no git).
 */
async function triggerDryRun() {
    showStatus('Triggering dry run...', 'info');
    const ok = await dispatchWorkflow('daily-blog-generator.yml', { dry_run: 'true' });
    showStatus(
        ok ? 'Dry run triggered! Check GitHub Actions for results.' : 'Failed to trigger.',
        ok ? 'success' : 'error'
    );
}

/**
 * Trigger weekly cleanup workflow.
 */
async function triggerCleanup() {
    showStatus('Triggering cleanup...', 'info');
    const ok = await dispatchWorkflow('weekly-cleanup.yml');
    showStatus(
        ok ? 'Cleanup triggered!' : 'Failed to trigger.',
        ok ? 'success' : 'error'
    );
}

/**
 * Update the cron schedule in the workflow YAML via GitHub API.
 */
async function updateWorkflowSchedule(newCron) {
    const headers = ghHeaders();
    if (!headers) return false;

    try {
        // Get current file
        const getResp = await fetch(
            `https://api.github.com/repos/${REPO}/contents/.github/workflows/daily-blog-generator.yml`,
            { headers }
        );
        if (!getResp.ok) return false;

        const fileData = await getResp.json();
        const content = atob(fileData.content);

        // Replace cron expression
        const updated = content.replace(
            /cron:\s*'[^']+'/,
            `cron: '${newCron}'`
        );

        // Commit the change
        const putResp = await fetch(
            `https://api.github.com/repos/${REPO}/contents/.github/workflows/daily-blog-generator.yml`,
            {
                method: 'PUT',
                headers,
                body: JSON.stringify({
                    message: `chore: update schedule to ${newCron}`,
                    content: btoa(updated),
                    sha: fileData.sha,
                }),
            }
        );

        return putResp.ok;
    } catch (e) {
        console.error('Schedule update error:', e);
        return false;
    }
}

/**
 * Update source config (enable/disable sources) via GitHub API.
 */
async function updateSourceConfig(changes) {
    const headers = ghHeaders();
    if (!headers) return false;

    try {
        // Get current file
        const getResp = await fetch(
            `https://api.github.com/repos/${REPO}/contents/config/sources.json`,
            { headers }
        );
        if (!getResp.ok) return false;

        const fileData = await getResp.json();
        const config = JSON.parse(atob(fileData.content));

        // Apply changes
        for (const [source, enabled] of Object.entries(changes)) {
            if (config[source]) {
                config[source].enabled = enabled;
            }
        }

        // Commit
        const putResp = await fetch(
            `https://api.github.com/repos/${REPO}/contents/config/sources.json`,
            {
                method: 'PUT',
                headers,
                body: JSON.stringify({
                    message: 'chore: update source configuration',
                    content: btoa(JSON.stringify(config, null, 2)),
                    sha: fileData.sha,
                }),
            }
        );

        return putResp.ok;
    } catch (e) {
        console.error('Source config update error:', e);
        return false;
    }
}

/**
 * Show status message on the page.
 */
function showStatus(message, type) {
    const el = document.getElementById('actions-status');
    if (el) {
        el.textContent = message;
        el.className = `actions-note ${type}`;
    }
}
