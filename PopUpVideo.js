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
    const GITHUB_FACTS_URL = 'https://raw.githubusercontent.com/NotMedic/PopUpVideo/main/facts/';
    const LOCAL_API_URL = 'http://localhost:5000/generate-facts';
    
    let currentVideoId = null;
    let currentVideoTitle = null;  // Track the current video's title
    let facts = [];
    let activePopup = null;
    let videoElement = null;
    let factsLoaded = false;
    let videoObserver = null;
    let logoShown = false;  // Track if logo has been shown for this video

    // Function to get current video ID from URL
    function getCurrentVideoId() {
        const urlParams = new URLSearchParams(window.location.search);
        return urlParams.get('v');
    }

    // Initialize for the current video
    function initializeForVideo() {
        const newVideoId = getCurrentVideoId();
        
        if (!newVideoId) {
            console.log('%c[PopUpFacts] No video ID found — waiting...', 'color: orange;');
            return;
        }

        // Check if this is a new video
        if (newVideoId === currentVideoId) {
            return; // Same video, do nothing
        }

        console.log('%c[PopUpFacts] New video detected!', 'color: lime; font-weight: bold;', newVideoId);
        
        // Reset state for new video
        currentVideoId = newVideoId;
        currentVideoTitle = null;  // Clear the old title
        facts = [];
        factsLoaded = false;
        logoShown = false;  // Reset logo for new video
        hidePopup(); // Clear any active popup
        
        // Load facts for the new video
        loadFacts();
        
        // Reinitialize video element observer
        setupVideoObserver();
    }

    // Initial check
    initializeForVideo();

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
        // Get video title from page - simpler approach
        let videoTitle = 'Unknown Title';
        
        // Method 1: Try the title element (most accurate)
        const titleElement = document.querySelector('h1.ytd-watch-metadata yt-formatted-string') || 
                            document.querySelector('h1.title.ytd-video-primary-info-renderer') ||
                            document.querySelector('h1 yt-formatted-string.ytd-watch-metadata');
        
        if (titleElement && titleElement.textContent.trim()) {
            videoTitle = titleElement.textContent.trim();
        } else {
            // Method 2: Fallback to document.title and strip " - YouTube"
            const docTitle = document.title.replace(/ - YouTube$/, '').trim();
            if (docTitle && docTitle !== 'YouTube') {
                videoTitle = docTitle;
            }
        }
        
        // Store the title for this video
        currentVideoTitle = videoTitle;
        
        console.log('[PopUpFacts] Calling local API to generate facts...');
        console.log('[PopUpFacts] Video ID:', currentVideoId);
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
                        
                        // Check if video was skipped (not a music video)
                        if (result.source === 'skipped') {
                            console.log('%c[PopUpFacts] Video skipped - not a music video', 'color: orange; font-weight: bold;');
                            console.log('[PopUpFacts] Reason:', result.reason);
                            factsLoaded = true; // Mark as loaded to prevent retries
                            facts = []; // Empty facts array
                            return;
                        }
                        
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

    // Watch for YouTube's navigation finish event (fires when page is fully loaded)
    window.addEventListener('yt-navigate-finish', function() {
        console.log('[PopUpFacts] YouTube navigation finished, checking for new video...');
        // Small delay to ensure DOM is fully updated
        setTimeout(() => {
            initializeForVideo();
        }, 500);
    });

    // Robust way to wait for video element using MutationObserver
    function setupVideoObserver() {
        // Disconnect existing observer if any
        if (videoObserver) {
            videoObserver.disconnect();
        }

        console.log('[PopUpFacts] Setting up video observer for video:', currentVideoId);

        videoObserver = new MutationObserver(() => {
            const newVideoElement = document.querySelector('video');

            if (newVideoElement && newVideoElement !== videoElement) {
                console.log('%c[PopUpFacts] VIDEO ELEMENT FOUND!', 'color: lime; font-weight: bold;', newVideoElement);
                videoElement = newVideoElement;
                videoObserver.disconnect();
                initPopups(videoElement);
            }
        });

        videoObserver.observe(document.documentElement, {
            childList: true,
            subtree: true
        });

        // Check immediately if video element already exists
        const existingVideo = document.querySelector('video');
        if (existingVideo) {
            console.log('%c[PopUpFacts] VIDEO ELEMENT ALREADY EXISTS!', 'color: lime; font-weight: bold;');
            videoElement = existingVideo;
            videoObserver.disconnect();
            initPopups(videoElement);
        }
    }

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
            const currentTime = Math.floor(video.currentTime);

            // Show Pop Up Video logo at the start (only once)
            if (currentTime <= 2 && !logoShown) {
                showLogo();
                logoShown = true;
            }

            if (!factsLoaded) return; // Wait for facts to load
            
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

    function showLogo() {
        console.log('%c[PopUpFacts] Showing Pop Up Video logo', 'color: cyan; font-weight: bold;');

        // Create logo container
        const logo = document.createElement('div');
        logo.style.position = 'fixed';
        logo.style.top = '50%';
        logo.style.left = '50%';
        logo.style.transform = 'translate(-50%, -50%)';
        logo.style.zIndex = '10001';
        logo.style.pointerEvents = 'none';
        logo.style.opacity = '0';
        logo.style.transition = 'opacity 0.5s';
        
        // Create the main box
        const box = document.createElement('div');
        box.style.background = 'linear-gradient(135deg, #000000 0%, #1a1a1a 100%)';
        box.style.padding = '30px 50px';
        box.style.borderRadius = '20px';
        box.style.border = '4px solid #00a8e8';
        box.style.boxShadow = '0 0 30px rgba(0, 168, 232, 0.5), 0 8px 30px rgba(0, 0, 0, 0.8)';
        box.style.textAlign = 'center';
        box.style.position = 'relative';
        
        // Create the text container
        const textDiv = document.createElement('div');
        textDiv.style.fontFamily = "'Impact', 'Arial Black', sans-serif";
        textDiv.style.fontSize = '48px';
        textDiv.style.fontWeight = 'bold';
        textDiv.style.color = '#ffffff';
        textDiv.style.textShadow = '0 0 10px #00a8e8, 0 0 20px #00a8e8, 3px 3px 6px rgba(0, 0, 0, 0.8)';
        textDiv.style.letterSpacing = '4px';
        textDiv.style.marginBottom = '5px';
        
        // Create text spans
        const span1 = document.createElement('span');
        span1.style.color = '#00d4ff';
        span1.textContent = 'POP';
        
        const span2 = document.createElement('span');
        span2.style.color = '#ffffff';
        span2.textContent = ' UP ';
        
        const span3 = document.createElement('span');
        span3.style.color = '#00d4ff';
        span3.textContent = 'VIDEO';
        
        textDiv.appendChild(span1);
        textDiv.appendChild(span2);
        textDiv.appendChild(span3);
        
        // Create the bubble circle
        const circle = document.createElement('div');
        circle.style.width = '30px';
        circle.style.height = '30px';
        circle.style.background = '#00a8e8';
        circle.style.borderRadius = '50%';
        circle.style.margin = '10px auto 0';
        circle.style.boxShadow = '0 0 15px rgba(0, 168, 232, 0.8)';
        circle.style.position = 'relative';
        
        // Create inner white dot
        const innerDot = document.createElement('div');
        innerDot.style.position = 'absolute';
        innerDot.style.top = '50%';
        innerDot.style.left = '50%';
        innerDot.style.transform = 'translate(-50%, -50%)';
        innerDot.style.width = '12px';
        innerDot.style.height = '12px';
        innerDot.style.background = 'white';
        innerDot.style.borderRadius = '50%';
        
        circle.appendChild(innerDot);
        
        // Assemble everything
        box.appendChild(textDiv);
        box.appendChild(circle);
        logo.appendChild(box);
        document.body.appendChild(logo);

        // Fade in
        setTimeout(() => {
            logo.style.opacity = '1';
        }, 100);

        // Fade out after 3 seconds
        setTimeout(() => {
            logo.style.opacity = '0';
            setTimeout(() => {
                logo.remove();
                console.log('[PopUpFacts] Logo removed');
            }, 500);
        }, 3000);
    }

    function showPopup(text) {
        console.log('%c[PopUpFacts] showPopup triggered:', 'color: cyan;', text);

        hidePopup();

        // Create popup container
        const popup = document.createElement('div');
        popup.style.position = 'fixed';
        popup.style.zIndex = '10000';
        popup.style.pointerEvents = 'none';
        popup.style.transition = 'opacity 0.5s';
        popup.style.opacity = '1';

        // Random position (avoid edges)
        const positionsBottom = ['8%', '15%', '25%', '65%', '75%'];
        const positionsLeft   = ['5%', '15%', '25%', '60%', '70%'];
        popup.style.bottom = positionsBottom[Math.floor(Math.random() * positionsBottom.length)];
        popup.style.left   = positionsLeft[Math.floor(Math.random() * positionsLeft.length)];

        // Create the main bubble
        const bubble = document.createElement('div');
        bubble.style.background = 'linear-gradient(135deg, #ffeb3b 0%, #fdd835 100%)';
        bubble.style.color = '#000000';
        bubble.style.padding = '16px 24px';
        bubble.style.borderRadius = '20px';
        bubble.style.fontSize = '18px';
        bubble.style.fontWeight = 'bold';
        bubble.style.fontFamily = "'Arial Black', 'Arial', sans-serif";
        bubble.style.maxWidth = '400px';
        bubble.style.textAlign = 'center';
        bubble.style.boxShadow = '0 0 0 4px #000000, 0 0 0 6px #ffeb3b, 0 8px 30px rgba(0, 0, 0, 0.7)';
        bubble.style.border = '3px solid #000000';
        bubble.style.position = 'relative';
        bubble.style.lineHeight = '1.3';
        bubble.textContent = text;

        // Create bubble tail (pointer)
        const tail = document.createElement('div');
        tail.style.position = 'absolute';
        tail.style.bottom = '-15px';
        tail.style.left = '30px';
        tail.style.width = '0';
        tail.style.height = '0';
        tail.style.borderLeft = '15px solid transparent';
        tail.style.borderRight = '15px solid transparent';
        tail.style.borderTop = '18px solid #000000';
        
        // Inner tail (yellow part)
        const tailInner = document.createElement('div');
        tailInner.style.position = 'absolute';
        tailInner.style.bottom = '3px';
        tailInner.style.left = '-12px';
        tailInner.style.width = '0';
        tailInner.style.height = '0';
        tailInner.style.borderLeft = '12px solid transparent';
        tailInner.style.borderRight = '12px solid transparent';
        tailInner.style.borderTop = '15px solid #fdd835';
        
        tail.appendChild(tailInner);
        bubble.appendChild(tail);

        // Add small decorative circle (Pop Up Video signature)
        const circle = document.createElement('div');
        circle.style.position = 'absolute';
        circle.style.top = '-8px';
        circle.style.right = '-8px';
        circle.style.width = '20px';
        circle.style.height = '20px';
        circle.style.background = '#ffeb3b';
        circle.style.border = '3px solid #000000';
        circle.style.borderRadius = '50%';
        circle.style.boxShadow = '0 2px 8px rgba(0, 0, 0, 0.4)';
        
        bubble.appendChild(circle);

        popup.appendChild(bubble);

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