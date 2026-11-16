/* ATRIA — sem fetch handler ou CacheStorage para dados privados. */
self.addEventListener("install",()=>{self.skipWaiting();});
self.addEventListener("activate",e=>{e.waitUntil(self.clients.claim());});
