"""Downloads the bike routes from NYC Open Data and saves the processed snapshot that the app reads."""

from bike_routes.repositories import RouteRepository

if __name__ == "__main__":
    RouteRepository().save_snapshot()
