from bike_routes.data import load_routes
from bike_routes.views import render_map

routes = load_routes()
render_map(routes)
