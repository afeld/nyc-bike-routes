from bike_routes.data import load_routes
from bike_routes.views import get_yearly_miles

print(get_yearly_miles(load_routes()).to_json(orient="records"))
