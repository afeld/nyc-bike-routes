import streamlit as st

from bike_routes.data import load_routes
from bike_routes.views import render_projects

st.subheader("Projects")
st.markdown(
    "Route miles installed on each street, by year. _Replaced_ shows the type of route that was there before, if any, so upgrades show up as e.g. Conventional → Protected."
)
with st.expander("How this works"):
    st.markdown(
        """\
        The city's data doesn't have projects as such, just street segments with the dates each type of route was installed and retired. To piece together what changed:

        - **Replacements:** A route counts as _replacing_ another if it was installed on the same street segment within 60 days of that one being retired. The rest are counted as _new_. The data has a field that's meant to link a route to the one it superseded, but it's rarely filled in, so this matches on segments instead.
        - **Projects:** Segments are grouped by street, borough, year installed, type, and the type replaced. Street types are standardized first (e.g. "Park Avenue" and "Park Av" are the same street). A project that spanned multiple years, or that mixes route types, shows up as multiple rows.

        Some caveats:

        - **A replacement isn't always an upgrade.** It can also be a redesign of the same type, or an attribute change in the data. Some lanes became _shared_ when the street became an [Open Street](https://www.nyc.gov/html/dot/html/pedestrians/openstreets.shtml), which is a lower class in the data but arguably better for cycling.
        - **Replacements are likely undercounted.** If a street was split into different segments when it was redone, the new route is counted as new.
        - **Install dates are approximate**, per the data dictionary, and some routes have placeholder dates (January 1, 1970).
        """
    )

routes = load_routes()
render_projects(routes)
