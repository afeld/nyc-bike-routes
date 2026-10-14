import { readFileSync } from "node:fs";

const metadata = JSON.parse(readFileSync("data/metadata.json", "utf-8"));
const lastUpdated = metadata.dataset_last_updated?.slice(0, 10) ?? "Unknown";

export default {
  title: "NYC bike routes over time",
  root: "src",
  output: "dist",
  pages: [
    { name: "Map", path: "/" },
    { name: "Miles", path: "/miles" },
    { name: "Mayors", path: "/mayors" },
  ],
  // the data loaders run from the project root and import bike_routes from it
  interpreters: { ".py": ["env", "PYTHONPATH=.", "uv", "run", "python"] },
  head: `<link rel="icon" href="data:image/svg+xml,<svg xmlns=%22http://www.w3.org/2000/svg%22 viewBox=%220 0 100 100%22><text y=%22.9em%22 font-size=%2290%22>🚲</text></svg>">`,
  footer: `Uses <a href="https://data.cityofnewyork.us/dataset/New-York-City-Bike-Routes/mzxg-pwib/about_data">Bike Routes from NYC Open Data</a>. Route length is measured in the <a href="https://epsg.io/2263">EPSG:2263 coordinate system</a> and converted from feet to miles. Dataset updated <span id="last-updated">${lastUpdated}</span>.<br><a href="https://www.nyc.gov/html/dot/html/bicyclists/bikemaps.shtml">General NYC bike map info.</a> App created by <a href="https://api.afeld.me">Aidan Feldman</a>.`,
};
