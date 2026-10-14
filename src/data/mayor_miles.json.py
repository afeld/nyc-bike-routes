from bike_routes.data import load_routes
from bike_routes.views import get_mayors

print(get_mayors(load_routes()).to_json(orient="records", date_format="iso"))
