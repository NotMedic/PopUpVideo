// ==UserScript==
// @name         YouTube Pop Up Video - Universal
// @namespace    http://tampermonkey.net/
// @version      2.0
// @description  Pop-up fun facts for any music video with GitHub caching
// @author       You
// @match        https://www.youtube.com/watch*
// @grant        GM_xmlhttpRequest
// @connect      raw.githubusercontent.com
// @connect      localhost
// ==/UserScript==

(function() {
    'use strict';

    console.log('%c[PopUpFacts] Script started', 'color: cyan; font-weight: bold;');

    // Configuration
    const GITHUB_FACTS_URL = 'https://raw.githubusercontent.com/YOUR_USERNAME/PopUpVideo/main/facts/';
    const LOCAL_API_URL = 'http://localhost:5000/generate-facts';
    
    const urlParams = new URLSearchParams(window.location.search);
    const currentVideoId = urlParams.get('v');

    console.log('[PopUpFacts] Current video ID:', currentVideoId);

    if (!currentVideoId) {
        console.log('%c[PopUpFacts] No video ID found — exiting.', 'color: orange;');
        return;
    }

    let facts = [];
    let activePopup = null;
    let videoElement = null;
    let factsLoaded = false;

    // Fetch facts from GitHub or generate via API
    function loadFacts() {
        console.log('[PopUpFacts] Attempting to load facts for video:', currentVideoId);
        
        // Try GitHub first
        const githubUrl = `${GITHUB_FACTS_URL}${currentVideoId}.json`;
        console.log('[PopUpFacts] Trying GitHub cache:', githubUrl);
        
        GM_xmlhttpRequest({
            method: 'GET',
            url: githubUrl,
            onload: function(response) {
                if (response.status === 200) {
                    try {
                        const data = JSON.parse(response.responseText);
                        facts = data.facts;
                        factsLoaded = true;
                        console.log('%c[PopUpFacts] Facts loaded from GitHub cache!', 'color: lime; font-weight: bold;', facts.length, 'facts');
                    } catch (e) {
                        console.error('[PopUpFacts] Error parsing GitHub facts:', e);
                        generateFactsFromAPI();
                    }
                } else {
                    console.log('[PopUpFacts] No GitHub cache found, calling local API...');
                    generateFactsFromAPI();
                }
            },
            onerror: function(error) {
                console.log('[PopUpFacts] GitHub fetch failed, calling local API...', error);
                generateFactsFromAPI();
            }
        });
    }

    function generateFactsFromAPI() {
        // Get video title from page
        const titleElement = document.querySelector('h1.ytd-watch-metadata yt-formatted-string');
        const videoTitle = titleElement ? titleElement.textContent.trim() : 'Unknown Title';
        
        console.log('[PopUpFacts] Calling local API to generate facts...');
        console.log('[PopUpFacts] Video title:', videoTitle);
        
        GM_xmlhttpRequest({
            method: 'POST',
            url: LOCAL_API_URL,
            headers: {
                'Content-Type': 'application/json'
            },
            data: JSON.stringify({
                video_id: currentVideoId,
                title: videoTitle
            }),
            onload: function(response) {
                if (response.status === 200) {
                    try {
                        const result = JSON.parse(response.responseText);
                        facts = result.data.facts;
                        factsLoaded = true;
                        console.log('%c[PopUpFacts] Facts generated successfully!', 'color: lime; font-weight: bold;', facts.length, 'facts');
                        console.log('[PopUpFacts] Facts saved locally. Push to GitHub to share!');
                    } catch (e) {
                        console.error('[PopUpFacts] Error parsing API response:', e);
                        showErrorPopup('Failed to generate facts');
                    }
                } else {
                    console.error('[PopUpFacts] API call failed:', response.status, response.responseText);
                    showErrorPopup('Local API not running. Start backend server!');
                }
            },
            onerror: function(error) {
                console.error('[PopUpFacts] API request error:', error);
                showErrorPopup('Cannot connect to local API. Is the backend running?');
            }
        });
    }

    function showErrorPopup(message) {
        console.log('[PopUpFacts] Showing error popup:', message);
        const popup = document.createElement('div');
        popup.textContent = message;
        popup.style.position = 'fixed';
        popup.style.top = '20px';
        popup.style.left = '50%';
        popup.style.transform = 'translateX(-50%)';
        popup.style.background = 'rgba(255, 50, 50, 0.95)';
        popup.style.color = 'white';
        popup.style.padding = '15px 25px';
        popup.style.borderRadius = '8px';
        popup.style.fontSize = '16px';
        popup.style.fontWeight = 'bold';
        popup.style.zIndex = '10000';
        popup.style.boxShadow = '0 4px 12px rgba(0,0,0,0.5)';
        document.body.appendChild(popup);
        
        setTimeout(() => {
            popup.remove();
        }, 5000);
    }

    // Start loading facts
    loadFacts();

    // Robust way to wait for video element using MutationObserver
    console.log('[PopUpFacts] Starting MutationObserver to detect video element...');

    const observer = new MutationObserver(() => {
        videoElement = document.querySelector('video');

        if (videoElement) {
            console.log('%c[PopUpFacts] VIDEO ELEMENT FOUND!', 'color: lime; font-weight: bold;', videoElement);
            observer.disconnect();
            initPopups(videoElement);
        }
    });

    observer.observe(document.documentElement, {
        childList: true,
        subtree: true
    });

    function initPopups(video) {
        console.log('%c[PopUpFacts] initPopups — attaching timeupdate listener', 'color: yellow; background: black;');

        video.addEventListener('timeupdate', () => {
            if (!factsLoaded) return; // Wait for facts to load
            
            const currentTime = Math.floor(video.currentTime);

            const fact = facts.find(f => f.time === currentTime);
            if (fact) {
                console.log('%c[PopUpFacts] FACT MATCH!', 'color: magenta; font-weight: bold;', fact.text);
                if (activePopup) {
                    console.log('[PopUpFacts] Skipping — popup already active');
                } else {
                    showPopup(fact.text);
                }
            }
        });

        video.addEventListener('pause', () => { console.log('[PopUpFacts] Paused'); hidePopup(); });
        video.addEventListener('seeked', () => { console.log('[PopUpFacts] Seeked'); hidePopup(); });
        video.addEventListener('seeking', () => { console.log('[PopUpFacts] Seeking'); hidePopup(); });
    }

    function showPopup(text) {
        console.log('%c[PopUpFacts] showPopup triggered:', 'color: cyan;', text);

        hidePopup();

        const popup = document.createElement('div');
        popup.textContent = text;
        popup.style.position = 'fixed';                  // Fixed to viewport
        popup.style.background = 'rgba(255, 255, 0, 0.95)';
        popup.style.color = 'black';
        popup.style.padding = '15px 25px';
        popup.style.borderRadius = '12px';
        popup.style.fontSize = '20px';
        popup.style.fontWeight = 'bold';
        popup.style.fontFamily = 'Arial, sans-serif';
        popup.style.maxWidth = '70%';
        popup.style.textAlign = 'center';
        popup.style.boxShadow = '0 8px 20px rgba(0,0,0,0.8)';
        popup.style.zIndex = '10000';                    // Very high
        popup.style.pointerEvents = 'none';
        popup.style.transition = 'opacity 0.5s';
        popup.style.opacity = '1';

        // Random position (avoid edges)
        const positionsBottom = ['8%', '15%', '25%', '65%', '75%'];
        const positionsLeft   = ['5%', '15%', '25%', '60%', '70%'];
        popup.style.bottom = positionsBottom[Math.floor(Math.random() * positionsBottom.length)];
        popup.style.left   = positionsLeft[Math.floor(Math.random() * positionsLeft.length)];

        console.log(`[PopUpFacts] Positioning: bottom=${popup.style.bottom}, left=${popup.style.left}`);

        document.body.appendChild(popup);
        activePopup = popup;

        console.log('%c[PopUpFacts] Popup appended to body!', 'color: lime;', popup);

        setTimeout(() => {
            console.log('[PopUpFacts] Auto-hide starting');
            hidePopup();
        }, 8000);
    }

    function hidePopup() {
        if (activePopup) {
            console.log('%c[PopUpFacts] hidePopup — fading out', 'color: orange;');
            activePopup.style.opacity = '0';
            setTimeout(() => {
                if (activePopup && activePopup.parentNode) {
                    activePopup.remove();
                    console.log('[PopUpFacts] Popup removed from DOM');
                }
                activePopup = null;
            }, 600);
        }
    }

})();