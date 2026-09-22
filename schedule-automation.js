'use strict';

const path = require('path');
const os = require('os');
const { chromium } = require('playwright');

// The app's normal entry point. Letting mysource1.deloitte.com generate its
// own OAuth authorize redirect keeps the state/nonce fresh on every run.
// A raw authorize URL (with an embedded state/nonce from one specific
// login attempt) can be overridden here if you specifically need it, but
// it will typically stop working once that state expires or is consumed.
const TARGET_URL = process.env.MYSOURCE_URL || 'https://mysource1.deloitte.com/';

// Edge profile to reuse so existing Windows/SSO session cookies apply.
const USER_DATA_DIR =
  process.env.EDGE_USER_DATA_DIR ||
  path.join(os.homedir(), 'AppData', 'Local', 'Microsoft', 'Edge', 'User Data');
const PROFILE_DIRECTORY = process.env.EDGE_PROFILE_DIRECTORY || 'Default';

const NAV_TIMEOUT_MS = Number(process.env.NAV_TIMEOUT_MS || 60000);
const CLICK_TIMEOUT_MS = Number(process.env.CLICK_TIMEOUT_MS || 90000);

function log(message) {
  console.log(`[${new Date().toISOString()}] ${message}`);
}

async function run() {
  log('Launching Edge with your existing profile...');
  const context = await chromium.launchPersistentContext(USER_DATA_DIR, {
    channel: 'msedge',
    headless: false,
    viewport: null,
    args: [`--profile-directory=${PROFILE_DIRECTORY}`],
  });

  const page = context.pages()[0] ?? (await context.newPage());

  try {
    log(`Navigating to ${TARGET_URL} ...`);
    await page.goto(TARGET_URL, { waitUntil: 'domcontentloaded', timeout: NAV_TIMEOUT_MS });
    await page.waitForLoadState('networkidle', { timeout: NAV_TIMEOUT_MS }).catch(() => {});

    log('Waiting for "Go to Schedule" button...');
    const goToScheduleBtn = page.locator('button.js-LinktoMonth', { hasText: 'Go to Schedule' });
    await goToScheduleBtn.waitFor({ state: 'visible', timeout: CLICK_TIMEOUT_MS });
    await goToScheduleBtn.click();
    log('Clicked "Go to Schedule".');

    await page.waitForLoadState('networkidle', { timeout: NAV_TIMEOUT_MS }).catch(() => {});

    log('Waiting for "Confirm Schedule" button...');
    const confirmBtn = page.locator('button[data-action="schedule-confirm"]', {
      hasText: 'Confirm Schedule',
    });
    await confirmBtn.waitFor({ state: 'visible', timeout: CLICK_TIMEOUT_MS });
    await confirmBtn.click();
    log('Clicked "Confirm Schedule". Done.');

    await page.waitForTimeout(3000);
  } catch (err) {
    log(`Automation failed: ${err.message}`);
    log(
      'If this timed out waiting for a button, the page likely stopped at a sign-in/MFA ' +
        'prompt instead of reaching MySource. Run once interactively (node schedule-automation.js) ' +
        'to complete that sign-in manually; the session should then persist in this Edge profile.'
    );
    process.exitCode = 1;
  } finally {
    await context.close();
  }
}

run();
