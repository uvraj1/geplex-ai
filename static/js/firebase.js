// static/js/firebase.js
// Firebase App and Analytics Initialization for GepLex AI Assistant

import { initializeApp, getApps, getApp } from "https://www.gstatic.com/firebasejs/10.12.5/firebase-app.js";
import { getAnalytics, isSupported, logEvent } from "https://www.gstatic.com/firebasejs/10.12.5/firebase-analytics.js";

// Your web app's Firebase configuration
export const firebaseConfig = (window.GEPLEX_DEPLOYMENT && window.GEPLEX_DEPLOYMENT.firebaseConfig) || {
  apiKey: "AIzaSyCvefrQ-bJZ_mr97j_aLiYptlfKYb3blAs",
  authDomain: "geplex-ai.firebaseapp.com",
  databaseURL: "https://geplex-ai-default-rtdb.firebaseio.com",
  projectId: "geplex-ai",
  storageBucket: "geplex-ai.firebasestorage.app",
  messagingSenderId: "587292925892",
  appId: "1:587292925892:web:1450a207788d49a379ce91",
  measurementId: "G-R0EX7E2VYG"
};

// Initialize Firebase
export const app = getApps().length ? getApp() : initializeApp(firebaseConfig);

// Initialize Analytics (with safe environment support check)
export let analytics = null;
if (typeof window !== "undefined") {
  isSupported().then((supported) => {
    if (supported) {
      analytics = getAnalytics(app);
      window.firebaseAnalytics = analytics;
      try {
        logEvent(analytics, "app_initialized", {
          app_name: "GepLex",
          timestamp: new Date().toISOString()
        });
      } catch (_) {}
    }
  }).catch((err) => {
    console.debug("[Firebase] Analytics not supported in this environment:", err);
  });
}

// Global attachment for convenience
window.firebaseApp = app;
window.firebaseConfig = firebaseConfig;

export function trackEvent(eventName, eventParams = {}) {
  if (analytics) {
    try {
      logEvent(analytics, eventName, eventParams);
    } catch (e) {
      console.debug(`[Firebase] Error logging event ${eventName}:`, e);
    }
  }
}

export default app;
