// names come from the data dictionary:
// https://data.cityofnewyork.us/dataset/New-York-City-Bike-Routes/mzxg-pwib/about_data
// colors come from the official map:
// https://www.nyc.gov/html/dot/html/bicyclists/bikemaps.shtml
export const FACILITY_TYPES = [
  { code: "I", name: "Protected", color: "#429058" },
  { code: "II", name: "Conventional", color: "#53b5e9" },
  { code: "III", name: "Shared lane / signed route", color: "#a864a3" },
  { code: "L", name: "Link", color: "#acce67" },
].map((type) => ({ ...type, label: `${type.name} (${type.code})` }));
