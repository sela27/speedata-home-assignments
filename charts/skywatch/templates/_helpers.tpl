{{/*
Names and labels shared by the templates. All of a component's resources
(ConfigMap, Deployment, Service, Ingress, HPA) share one name, skywatch-<component>.
*/}}

{{/* Labels on every resource. */}}
{{- define "skywatch.labels" -}}
helm.sh/chart: {{ .Chart.Name }}-{{ .Chart.Version }}
app.kubernetes.io/managed-by: {{ .Release.Service }}
{{- end }}

{{- define "skywatch.frontend.name" -}}
{{ .Chart.Name }}-frontend
{{- end }}

{{/*
The labels the frontend's Deployment and Service select its pods by.
A Deployment's selector can't change after it is created, so neither can these.
*/}}
{{- define "skywatch.frontend.selectorLabels" -}}
app.kubernetes.io/name: {{ .Chart.Name }}
app.kubernetes.io/component: frontend
{{- end }}

{{- define "skywatch.backend.name" -}}
{{ .Chart.Name }}-backend
{{- end }}

{{/* The labels the backend's Deployment and Service select its pods by (as above). */}}
{{- define "skywatch.backend.selectorLabels" -}}
app.kubernetes.io/name: {{ .Chart.Name }}
app.kubernetes.io/component: backend
{{- end }}
