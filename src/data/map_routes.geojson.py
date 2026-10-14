from bike_routes.repositories import DATA_DIR, MAP_ROUTES_FILE

print((DATA_DIR / MAP_ROUTES_FILE).read_text())
