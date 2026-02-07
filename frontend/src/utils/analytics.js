/**
 * Lightweight conversion tracking for JarlPM landing page
 * 
 * Events tracked:
 * - landing_page_view
 * - click_generate_initiative
 * - click_see_example
 * - click_sign_in
 * - click_get_started
 * - click_generate_my_own (from preview modal)
 * - click_copy_prd
 * 
 * Currently logs to console. Ready to swap to real analytics (Mixpanel, Amplitude, PostHog, etc.)
 */

const TRACKING_ENABLED = true;

// Queue for events if we add a real analytics provider later
const eventQueue = [];

/**
 * Track a conversion event
 * @param {string} eventName - Name of the event
 * @param {object} properties - Additional properties to track
 */
export function trackEvent(eventName, properties = {}) {
  if (!TRACKING_ENABLED) return;

  const event = {
    event: eventName,
    timestamp: new Date().toISOString(),
    url: window.location.href,
    referrer: document.referrer || null,
    ...properties,
  };

  // Log to console for now (easy to see in dev tools)
  console.log('[JarlPM Track]', eventName, event);

  // Add to queue for future analytics integration
  eventQueue.push(event);

  // If we had a real analytics provider, we'd call it here:
  // mixpanel.track(eventName, properties);
  // amplitude.logEvent(eventName, properties);
  // posthog.capture(eventName, properties);

  // Optional: Send to backend for server-side tracking
  // This is commented out but ready to enable
  /*
  try {
    fetch('/api/analytics/track', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(event),
      keepalive: true, // Ensures request completes even if page navigates
    });
  } catch (e) {
    // Silent fail - don't break the app for analytics
  }
  */
}

/**
 * Track landing page view
 */
export function trackLandingPageView() {
  trackEvent('landing_page_view', {
    source: 'direct',
  });
}

/**
 * Track "Generate an Initiative" CTA click
 * @param {boolean} isLoggedIn - Whether user is logged in
 * @param {string} location - Where the button was clicked (hero, nav, etc.)
 */
export function trackGenerateInitiativeClick(isLoggedIn, location = 'hero') {
  trackEvent('click_generate_initiative', {
    is_logged_in: isLoggedIn,
    location,
    destination: isLoggedIn ? '/new' : '/signup?next=/new',
  });
}

/**
 * Track "See example output" click
 */
export function trackSeeExampleClick() {
  trackEvent('click_see_example', {
    location: 'hero',
  });
}

/**
 * Track "Sign in" click
 * @param {string} location - Where the button was clicked
 */
export function trackSignInClick(location = 'nav') {
  trackEvent('click_sign_in', {
    location,
  });
}

/**
 * Track "Get started" click
 * @param {string} location - Where the button was clicked
 */
export function trackGetStartedClick(location = 'nav') {
  trackEvent('click_get_started', {
    location,
  });
}

/**
 * Track "Generate my own" click from preview modal
 * @param {boolean} isLoggedIn - Whether user is logged in
 */
export function trackGenerateMyOwnClick(isLoggedIn) {
  trackEvent('click_generate_my_own', {
    is_logged_in: isLoggedIn,
    source: 'example_preview_modal',
    destination: isLoggedIn ? '/new' : '/signup?next=/new',
  });
}

/**
 * Track "Copy PRD snippet" click
 * @param {string} section - Which section was copied
 */
export function trackCopyPRDClick(section = 'full') {
  trackEvent('click_copy_prd', {
    section,
  });
}

/**
 * Track preview modal tab change
 * @param {string} tab - Which tab was selected (prd, stories, sprint)
 */
export function trackPreviewTabChange(tab) {
  trackEvent('preview_tab_change', {
    tab,
  });
}

/**
 * Get all tracked events (useful for debugging)
 */
export function getEventQueue() {
  return [...eventQueue];
}

export default {
  trackEvent,
  trackLandingPageView,
  trackGenerateInitiativeClick,
  trackSeeExampleClick,
  trackSignInClick,
  trackGetStartedClick,
  trackGenerateMyOwnClick,
  trackCopyPRDClick,
  trackPreviewTabChange,
  getEventQueue,
};
