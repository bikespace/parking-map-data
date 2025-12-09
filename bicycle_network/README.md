# City of Toronto Bicycle Network

Simplified version of the [City of Toronto bicycle network dataset](https://open.toronto.ca/dataset/cycling-network/), keeping only the columns relevant for use on bikespace.ca.


## Coding of Bike Route Types

The BikeSpace bicycle parking map currently categorizes cycling routes as follows, based on the "INFRA_HIGHORDER" property:

- Protected bike lane: includes "Cycle Track", "Cycle Track - Contraflow", and "Bi-Directional Cycle Track"
- Painted bike lane: includes "Bike Lane","Bike Lane - Buffered","Bike Lane - Contraflow","Contra-Flow Bike Lane","Contraflow"
- Multi-use or park trail: includes "Multi-Use Trail","Multi-Use Trail - Boulevard","Multi-Use Trail - Connector","Multi-Use Trail - Entrance","Multi-Use Trail - Existing Connector","Park Road"
- Unprotected bike route (e.g. sharrows): includes "Sharrows","Sharrows - Arterial","Sharrows - Arterial - Connector","Sharrows - Wayfinding"
- Unknown bike lane type: null or N/A values
