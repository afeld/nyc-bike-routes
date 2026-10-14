from bike_routes.data import load_routes
from bike_routes.views import get_cumulative_miles

cumulative_miles = get_cumulative_miles(load_routes()).rename_axis("year").reset_index()
print(cumulative_miles.to_json(orient="records", date_format="iso"))
