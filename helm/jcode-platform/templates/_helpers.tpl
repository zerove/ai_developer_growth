{{/*
Expand the name of the chart.
*/}}
{{- define "jcode-platform.name" -}}
{{- default .Chart.Name .Values.nameOverride | trunc 63 | trimSuffix "-" }}
{{- end }}

{{/*
Create a default fully qualified app name.
*/}}
{{- define "jcode-platform.fullname" -}}
{{- if and .Values (index .Values "fullnameOverride") }}
{{- index .Values "fullnameOverride" | trunc 63 | trimSuffix "-" }}
{{- else }}
{{- $name := default .Chart.Name (index .Values "nameOverride") }}
{{- if contains $name .Release.Name }}
{{- .Release.Name | trunc 63 | trimSuffix "-" }}
{{- else }}
{{- printf "%s-%s" .Release.Name $name | trunc 63 | trimSuffix "-" }}
{{- end }}
{{- end }}
{{- end }}

{{/*
Create chart name and version as used by the chart label.
*/}}
{{- define "jcode-platform.chart" -}}
{{- printf "%s-%s" .Chart.Name .Chart.Version | replace "+" "_" | trunc 63 | trimSuffix "-" }}
{{- end }}

{{/*
Common labels
*/}}
{{- define "jcode-platform.labels" -}}
helm.sh/chart: {{ include "jcode-platform.chart" . }}
{{ include "jcode-platform.selectorLabels" . }}
{{- if .Chart.AppVersion }}
app.kubernetes.io/version: {{ .Chart.AppVersion | quote }}
{{- end }}
app.kubernetes.io/managed-by: {{ .Release.Service }}
{{- end }}

{{/*
Selector labels
*/}}
{{- define "jcode-platform.selectorLabels" -}}
app.kubernetes.io/name: {{ include "jcode-platform.name" . }}
app.kubernetes.io/instance: {{ .Release.Name }}
{{- end }}

{{/*
Create the name of the service account to use
*/}}
{{- define "jcode-platform.serviceAccountName" -}}
{{- if .Values.global.serviceAccount.create }}
{{- default (include "jcode-platform.fullname" .) .Values.global.serviceAccount.name }}
{{- else }}
{{- default "default" .Values.global.serviceAccount.name }}
{{- end }}
{{- end }}