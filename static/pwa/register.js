/* ATRIA PWA: nenhum dado do sistema é armazenado offline. */
(()=>{if(!("serviceWorker"in navigator)||!window.isSecureContext)return;
window.addEventListener("load",()=>navigator.serviceWorker.register("/service-worker.js",{scope:"/"}).catch(()=>{}),{once:true});})();
