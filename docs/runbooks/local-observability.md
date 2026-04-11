# local-observability

## 1. Purpose

本 runbook 记录 Week05 本地最小可观测链路的启动、验证与排障步骤。

当前目标：

- 使用 Docker Compose 启动 Prometheus + Grafana
- Prometheus 先自抓自己，保证最小链路可见
- Grafana 通过 provisioning 自动加载 Prometheus datasource 与 dashboard
- 暂不把 Java `/actuator/prometheus` 作为本轮硬前提

---

## 2. File layout

~~~text
docker-compose.observability.yml
observability/prometheus/prometheus.yml
observability/grafana/provisioning/datasources/prometheus.yml
observability/grafana/provisioning/dashboards/dashboard-provider.yml
observability/grafana/dashboards/app-overview.json
docs/runbooks/local-observability.md
~~~

---

## 3. Start

~~~bash
docker compose -f docker-compose.observability.yml up -d
docker compose -f docker-compose.observability.yml ps
~~~

---

## 4. Verify

### 4.1 Prometheus readiness

~~~bash
curl -fsS http://127.0.0.1:9091/-/ready
~~~

期望返回：

~~~text
Prometheus Server is Ready.
~~~

### 4.2 Prometheus targets

打开：

~~~text
http://127.0.0.1:9091/targets
~~~

期望：

- 至少看到 `job="prometheus"` 为 `UP`

### 4.3 Grafana health

~~~bash
curl -fsS http://127.0.0.1:3001/api/health
~~~

### 4.4 Grafana dashboard

打开：

~~~text
http://127.0.0.1:3001
~~~

默认登录：

- user: `admin`
- password: `admin`

进入：

- Dashboards
- Week05
- App Overview

---

## 5. Stop

~~~bash
docker compose -f docker-compose.observability.yml down
~~~

---

## 6. Known next step

后续若接 Java 指标，需要补两件事：

1. Java 服务引入 `micrometer-registry-prometheus`
2. 显式暴露 `/actuator/prometheus`

然后再把 Prometheus job 加到 `prometheus.yml`。

---

## 7. Troubleshooting

### 7.1 Prometheus 起不来

先看：

~~~bash
docker compose -f docker-compose.observability.yml logs prometheus
~~~

重点查：

- YAML 缩进
- `prometheus.yml` 挂载路径
- 9090 端口占用

### 7.2 Grafana 没加载 dashboard

先看：

~~~bash
docker compose -f docker-compose.observability.yml logs grafana
~~~

重点查：

- provisioning 目录挂载路径
- dashboard JSON 是否是合法 JSON
- datasource uid 是否为 `prometheus`

### 7.3 Java 指标抓不到

当前阶段这是允许的；本轮最低要求只是先让 Prometheus 自抓成功。
