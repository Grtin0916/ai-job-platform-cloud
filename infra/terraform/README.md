# Terraform layout

## 1. 目标

当前阶段不追求立刻管理真实云资源，而是先固定 Terraform 目录布局，避免后续 dev 环境、模块抽取和 state 管理反复返工。

## 2. 目录职责

### envs/dev

用于放置开发环境入口。

后续这里将负责：

- 组合 modules
- 定义 dev 环境变量
- 维护 dev 环境的 provider / backend / main 入口
- 演示最小可执行 Terraform 配置

### modules

用于放置可复用模块。

后续这里将负责：

- 网络
- 计算
- 存储
- 监控
- 命名空间或平台基础资源等抽象模块

## 3. 当前约定

当前采用：

- `infra/terraform/envs/dev`：环境入口
- `infra/terraform/modules`：可复用模块

当前尚未落真实资源定义，但目录约定已冻结。

## 4. 后续进入方式

后续最小进入路径预计为：

    cd infra/terraform/envs/dev
    terraform init
    terraform validate
    terraform plan

## 5. 当前边界

当前不做：

- 真实云账号接入
- remote state
- module 版本管理
- 多环境 workspace 策略
- 复杂 provider 拆分

这些内容放到后续周次处理。
