/** Where the person's Clear · Tinted glass choice is kept on this device. */
export const GLASS_LOOK_KEY = "finboy.glass-look";

/**
 * Runs in the root layout's <head> before first paint, so a Tinted choice never flashes Clear.
 * Plain module (no React) so the server layout can import it.
 */
export const GLASS_LOOK_SCRIPT = `(function(){try{var l=localStorage.getItem(${JSON.stringify(GLASS_LOOK_KEY)});if(l==="clear"||l==="tinted")document.documentElement.setAttribute("data-glass-look",l)}catch(e){}})()`;
