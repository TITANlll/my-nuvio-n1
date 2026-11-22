import test from "node:test";
import assert from "node:assert/strict";
import {selectNewEpisodes} from "../src/index.js";

const now = new Date("2026-11-22T15:00:00.000Z");
function entry(id, airDate, watched=true) {
  return {
    show: {title:"Show "+id,year:2024,ids:{imdb:id},poster:"/abc123.jpg"},
    next_episode:{season:2,episode:4,title:"An episode",air_date:airDate}
  };
}
test("newest first, old unwatched episodes excluded, future excluded",()=>{
  const metas=selectNewEpisodes([
    entry("tt0000001","2026-11-12T10:00:00Z"),
    entry("tt0000002","2026-11-20T10:00:00Z"),
    entry("tt0000003","2026-11-24T10:00:00Z"),
    entry("tt0000004","2026-11-21T10:00:00Z")
  ],now);
  assert.deepEqual(metas.map(m=>m.id),["tt0000004","tt0000002"]);
  assert.match(metas[0].description,/S02E04/);
});
test("one card per show, supports TMDB fallback, skips malformed",()=>{
  const first=entry("tt0000001","2026-11-19T10:00:00Z");
  const second=entry("tt0000001","2026-11-21T10:00:00Z");
  const tmdb={show:{title:"Other",ids:{tmdb:123},poster:"/poster.jpg"},
    next_episode:{season:1,episode:1,air_date:"2026-11-18"}};
  const metas=selectNewEpisodes([first,second,tmdb,{show:{title:"Bad"},next_episode:{}},null],now);
  assert.equal(metas.length,2);
  assert.equal(metas.find(m=>m.id==="tt0000001")?.description.includes("2026-11-21"),true);
  assert.ok(metas.find(m=>m.id==="tmdb:123"));
});
