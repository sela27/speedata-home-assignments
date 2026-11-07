// The load for the dashboard and HPA demo. scripts/load.ps1 runs it in the k6 container.
// It asks the frontend's Ingress for pages, as a visitor's browser does, for 10 cities in turn.
import http from 'k6/http';
import exec from 'k6/execution';

// Each backend pod caches a City lookup for a day and a Weather report for 10 minutes, so
// however many pages k6 asks for, Open-Meteo gets a few calls per city per pod, and one
// forecast call per city per pod every 10 minutes.
const CITIES = ['Haifa', 'Berlin', 'Tokyo', 'London', 'Paris', 'Madrid', 'Rome', 'Cairo', 'Sydney', 'Toronto'];

export const options = {
  scenarios: {
    pages: {
      // A set number of pages per second, however fast they are answered.
      executor: 'ramping-arrival-rate',
      startRate: 1,
      timeUnit: '1s',
      // A page costs the backend about 2 ms of CPU, so 45 pages/s keep its 2 pods at about 90%
      // of their CPU request, above the HPA's 70% target: it scales them out to 3, at about 60%
      // each. The frontend stays at about 30% of its CPU limit.
      stages: [
        // The slow start fills both backend pods' caches before the full rate arrives.
        { target: 45, duration: '1m' },
        { target: 45, duration: '4m' },
      ],
      // A VU waits for its page, so slow pages need more VUs to keep the rate. At most 100
      // wait at once; k6 drops the pages beyond that, so a stalled app is not buried.
      preAllocatedVUs: 10,
      maxVUs: 100,
    },
  },
};

export default function () {
  const city = CITIES[exec.scenario.iterationInTest % CITIES.length];
  http.get(`http://skywatch.192-168-60-11.sslip.io/?city=${city}`);
}
