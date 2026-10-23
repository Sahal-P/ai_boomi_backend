"use client";

import { useGSAP } from "@gsap/react";
import gsap from "gsap";
import { ScrollTrigger } from "gsap/ScrollTrigger";

/**
 * One GSAP instance for the marketing page. Its ticker is the page's only animation clock:
 * Lenis (scroll), ScrollTrigger, tweens and both WebGL canvases advance in that order on
 * each tick, so 3D never lags a frame behind scrolled DOM.
 */
gsap.registerPlugin(ScrollTrigger, useGSAP);
// Keep real time after a long frame (tab switch, GC) instead of slowing the world down.
gsap.ticker.lagSmoothing(0);

export { gsap, ScrollTrigger, useGSAP };
