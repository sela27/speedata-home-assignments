# SkyWatch

A small weather-query app and the local Kubernetes platform that builds, ships and runs it through CI and GitOps.

## Language

### Application

**Weather report**:
The current temperature and conditions for one city, as shown to the user. It is a snapshot of now, not a forecast.
_Avoid_: forecast, weather result, weather data

**Conditions**:
A short human-readable description of the current weather, such as "Partly cloudy".
_Avoid_: weather code, status

**City lookup**:
Turning a city name the user typed into one specific place (name, country, coordinates). When several places share the name, the most populous one wins.
_Avoid_: search, geocoding

### Delivery

**Key flow**:
A code change pushed to `main` ending up running in the cluster with no manual cluster commands in between.
_Avoid_: deploy pipeline, CD flow

**Tag bump**:
The automated commit that points the deployment at the images just built for a commit.
_Avoid_: version update, image update commit

**Bring-up**:
Taking a clean machine to a fully running system by following the README.
_Avoid_: install, setup, provisioning (when meaning the whole sequence)

### Platform

**Node network**:
The private, fixed-address network shared by the host and the cluster nodes; all cluster traffic and host access to the cluster go over it.
_Avoid_: internal switch, mgmt network, second NIC

**Uplink**:
A node's connection to the internet, used only for outbound traffic such as package installs and image pulls.
_Avoid_: Default Switch network, NAT network
