// Private, dynamic Stremio/Nuvio catalog backed by the user's own MDBList Up Next.
// Do not publish MDBList keys or watch history in the public GitHub Pages site.
const RECENT_DAYS = 7;
const MAX_PAGES = 5; // 500 in-progress series at the API's 100-item page limit.
const MD_API = "https://api.mdblist.com/upnext";
const CORS = {
  "access-control-allow-origin": "*",
  "access-control-allow-methods": "GET, HEAD, OPTIONS",
  "access-control-allow-headers": "content-type",
  "content-type": "application/json; charset=utf-8",
  "cache-control": "private, no-store"
};

function respond(body, status = 200) {
  return new Response(JSON.stringify(body), { status, headers: CORS });
}

function posterUrl(poster) {
  if (typeof poster !== "string" || !poster.trim()) return undefined;
  if (poster.startsWith("https://image.tmdb.org/")) return poster;
  if (poster.startsWith("/") && /^\/[A-Za-z0-9/_\-.]+$/.test(poster)) {
    return "https://image.tmdb.org/t/p/w500" + poster;
  }
  return undefined;
}

export function selectNewEpisodes(items, now = new Date()) {
  const newestByShow = new Map();
  for (const item of (Array.isArray(items) ? items : [])) {
    const show = item?.show;
    const ep = item?.next_episode;
    if (!show || !ep || typeof ep.air_date !== "string") continue;
    const date = Date.parse(ep.air_date);
    // Include only next unwatched episodes aired within the last seven days.
    if (!Number.isFinite(date) || date > now.getTime() ||
        date < now.getTime() - RECENT_DAYS * 24 * 60 * 60 * 1000) continue;
    const imdb = show.ids?.imdb;
    const tmdb = show.ids?.tmdb;
    const id = (typeof imdb === "string" && /^tt\d+$/.test(imdb)) ? imdb
      : (Number.isInteger(Number(tmdb)) && Number(tmdb) > 0) ? "tmdb:" + tmdb
      : null;
    if (!id || !show.title) continue;
    const season = Number(ep.season), episode = Number(ep.episode);
    const episodeLabel = Number.isInteger(season) && Number.isInteger(episode)
      ? "S" + String(season).padStart(2,"0") + "E" + String(episode).padStart(2,"0")
      : "New episode";
    const candidate = {
      id, type: "series", name: show.title,
      ...(posterUrl(show.poster) ? { poster: posterUrl(show.poster) } : {}),
      ...(show.year ? { releaseInfo: String(show.year) } : {}),
      description: episodeLabel + " · " + (ep.title || "New episode") + " · Aired " +
        new Date(date).toISOString().slice(0,10)
    };
    const existing = newestByShow.get(id);
    if (!existing || existing.date < date) newestByShow.set(id,{date, candidate});
  }
  return [...newestByShow.values()]
    .sort((a,b) => b.date - a.date || a.candidate.name.localeCompare(b.candidate.name))
    .map(v => v.candidate);
}

async function loadUpNext(key) {
  const all = [];
  for (let page = 0; page < MAX_PAGES; page++) {
    const api = new URL(MD_API);
    api.searchParams.set("apikey",key);
    api.searchParams.set("limit","100");
    api.searchParams.set("offset",String(page*100));
    // Explicitly exclude an episode merely scheduled for "today" but not yet aired.
    api.searchParams.set("hide_unreleased","true");
    const reply = await fetch(api.toString(), {
      headers: { "accept": "application/json" }
    });
    if (!reply.ok) throw new Error("MDBList HTTP " + reply.status);
    const data = await reply.json();
    if (!data || !Array.isArray(data.items)) throw new Error("Invalid MDBList Up Next response");
    all.push(...data.items);
    if (!data.has_more || data.items.length < 100) break;
  }
  return all;
}

export default {
  async fetch(request, env) {
    if (request.method === "OPTIONS") return new Response(null, {status:204,headers:CORS});
    if (!["GET","HEAD"].includes(request.method)) return respond({error:"Method not allowed"},405);
    if (!env.MDBLIST_API_KEY || !env.ADDON_ACCESS_TOKEN ||
      env.ADDON_ACCESS_TOKEN.length < 24) {
      return respond({error:"Addon is not configured"},503);
    }
    const url = new URL(request.url);
    const parts = url.pathname.split("/").filter(Boolean);
    if (parts[0] !== env.ADDON_ACCESS_TOKEN) return respond({error:"Not found"},404);
    if (parts.length === 2 && parts[1] === "manifest.json") {
      return respond({
        id: "com.personal.mdblist.new-episodes",
        version: "1.0.0",
        name: "New Episodes",
        description: "Recently aired next unwatched episodes from your existing MDBList viewing history.",
        resources: ["catalog"],
        types: ["series"],
        catalogs: [{ type: "series", id: "my-new-episodes", name: "New Episodes" }],
        behaviorHints: { configurable: false, configurationRequired: false }
      });
    }
    if (parts.length === 4 && parts[1] === "catalog" &&
      parts[2] === "series" && parts[3] === "my-new-episodes.json") {
      try {
        const items = await loadUpNext(env.MDBLIST_API_KEY);
        return respond({metas:selectNewEpisodes(items)});
      } catch (err) {
        // Never echo the upstream URL, API key, or account history to clients.
        return respond({error:"MDBList is temporarily unavailable"},502);
      }
    }
    return respond({error:"Not found"},404);
  }
};
