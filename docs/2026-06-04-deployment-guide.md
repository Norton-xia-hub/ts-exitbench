# ts-exitbench 部署、测速与验收指南

本文档用于记录 `ts-exitbench` 第一版的实际落地流程，目标是让后续新增节点、客户端测速、Exit Node 验收都可以按步骤重复执行。

仓库地址：<https://github.com/Norton-xia-hub/ts-exitbench>
当前版本：`v0.1.1`

## 1. 工具目标

`ts-exitbench` 用于在本地客户端上测试当前网络到多个 Tailscale 节点的访问质量，辅助选择更合适的 Exit Node。

第一版支持：

- 从 Tailscale 自动发现节点
- Linux 节点运行测速 Agent
- 客户端执行延迟、上传、下载测速
- 生成 `report.html` 和 `report.json`
- 节点只监听 Tailscale IP，不暴露公网测速端口

## 2. 当前环境约定

- 客户端：Windows / macOS / Linux
- 海外节点：Linux
- 节点互联：Tailscale
- Agent 统一端口：`51234`
- 第一版共享 token 示例：

```text
K3T_e05o2Fj7NUpzgVUcY4XttRdQ5Bo64B0ftqFnDTs
```

后续新增节点时，建议继续使用同一个 token。

## 3. 在客户端准备项目

如果本地还没有项目：

```bash
git clone https://github.com/Norton-xia-hub/ts-exitbench.git
cd ts-exitbench
git checkout v0.1.1
```

macOS 如果安装了 Tailscale App 但终端找不到 `tailscale`，先执行：

```bash
export PATH="/Applications/Tailscale.app/Contents/MacOS:$PATH"
```

确认 Tailscale 命令可用：

```bash
tailscale status
```

## 4. 客户端配置

复制示例配置：

```bash
cp config.example.json config.json
```

编辑 `config.json`，至少把 `agent.token` 改成所有 Linux 节点统一使用的 token：

```json
{
  "agent": {
    "host": "TAILSCALE_IPV4_HERE",
    "port": 51234,
    "token": "K3T_e05o2Fj7NUpzgVUcY4XttRdQ5Bo64B0ftqFnDTs"
  }
}
```

说明：

- 客户端扫描时，真正的节点列表来自 `tailscale status --json`
- 客户端侧 `agent.host` 只是示例占位，不参与节点发现
- 当前最关键的是 `agent.token` 和 Linux 节点保持一致

## 5. 在新的 Linux 节点安装 Agent

### 5.1 Ubuntu 节点

如果节点已经安装并登录 Tailscale，执行：

```bash
sudo apt update
sudo apt install -y git python3
git clone https://github.com/Norton-xia-hub/ts-exitbench.git
cd ts-exitbench
git checkout v0.1.1
sudo TS_EXITBENCH_TOKEN='K3T_e05o2Fj7NUpzgVUcY4XttRdQ5Bo64B0ftqFnDTs' ./install-agent.sh
```

如果节点还没有安装 Tailscale，先执行：

```bash
curl -fsSL https://tailscale.com/install.sh | sh
sudo tailscale up
```

再执行安装命令。

### 5.2 非 Ubuntu 的 Linux 节点

如果系统不是 Ubuntu，请先确认：

```bash
cat /etc/os-release
python3 --version
```

第一版要求 Python `3.9+`。

如果 `python3` 太老，Agent 可能会报错：

```text
SyntaxError: future feature annotations is not defined
```

这种情况先升级 Python，再修改 systemd 里的 Python 路径。

常见检查命令：

```bash
python3 --version
cat /etc/os-release
```

## 6. Linux 节点安装完成后的验收

安装脚本完成后，执行：

```bash
sudo systemctl status ts-exitbench-agent
ss -lntp | grep 51234
tailscale ip -4
sudo cat /etc/ts-exitbench/config.json
```

通过标准：

- `ts-exitbench-agent` 为 `active (running)`
- `51234` 监听在节点的 `100.x.x.x` Tailscale IP 上
- 不是 `0.0.0.0:51234`
- `/etc/ts-exitbench/config.json` 中的 token 正确

示例：

```text
LISTEN 0 5 100.94.31.122:51234 0.0.0.0:*
```

这表示 Agent 只监听 Tailscale IP，是正确状态。

## 7. 客户端执行测速

### 7.1 先做短测

先验证链路和报告生成：

```bash
python3 -m ts_exitbench scan --config config.json --out report.html --speed --duration 5
```

生成文件：

- `report.html`
- `report.json`

### 7.2 正式测速

确认短测没问题后，再执行：

```bash
python3 -m ts_exitbench scan --config config.json --out report.html --speed --duration 30
```

这个结果更适合拿来判断 Exit Node。

## 8. report.json 主要字段说明

每个节点主要看这些字段：

- `online`：节点是否在线
- `exit_node_option`：节点是否可作为 Exit Node 候选
- `ping.raw`：Tailscale 原始探测结果
- `agent.ok`：测速 Agent 是否连通
- `download.mbps`：节点到客户端的下载速度
- `upload.mbps`：客户端到节点的上传速度
- `score`：当前版本的综合排序分数
- `rank`：排序名次

注意：

- 第一版的 `score` 是粗排，不一定完全等于真实体感
- 现阶段更应该结合 `ping.raw`、`upload.mbps`、`download.mbps` 一起判断

## 9. Exit Node 优秀度验收清单

### 9.1 基础连通

```bash
tailscale status
tailscale ip -4
sudo systemctl status ts-exitbench-agent
ss -lntp | grep 51234
```

通过标准：

- 节点在线
- Agent 正常运行
- 端口只监听在 Tailscale IP 上

### 9.2 客户端链路质量

```bash
python3 -m ts_exitbench scan --config config.json --out report.html --speed --duration 30
```

重点看：

- 延迟是否低
- 是否频繁走 DERP
- 上传速度是否稳定
- 下载速度是否正常

### 9.3 节点出口公网质量

在节点上执行：

```bash
curl ip.sb
curl -I https://www.google.com
curl -I https://chatgpt.com
curl -I https://www.youtube.com
```

通过标准：

- 能获取公网出口 IP
- Google 返回 `200`
- ChatGPT 能正常跳转或打开
- YouTube 返回 `200`

### 9.4 地区识别

```bash
curl https://ipinfo.io
```

或：

```bash
curl https://ifconfig.co/json
```

看国家、城市、ASN 是否符合预期。

### 9.5 实际使用体验

把该节点切为 Exit Node 后，在本机做真实体验测试：

- 打开 Google
- 打开 ChatGPT
- 打开 YouTube
- 观看 1080p 视频
- 访问日常网站
- SSH 到常用服务器

### 9.6 稳定性

在白天、晚高峰、深夜分别重复测速，观察：

- 延迟波动
- 上传速度波动
- 是否经常掉到 DERP
- 是否偶尔断流

## 10. 今天已确认的结论

- `oracle-ubuntu` 部署成功
- 客户端已可完成 5 秒短测与 30 秒正式测速
- 当前版本可以用来辅助选择 Exit Node
- 报告中的综合分数可参考，但不应完全替代人工判断
- 节点是否优秀，还要结合公网出口质量与实际使用体感

## 11. 后续建议

建议优先继续做这几件事：

1. 给所有海外 Linux 节点统一安装 Agent，并统一 token
2. 只保留真正需要参与 Exit Node 选择的节点
3. 对候选节点重复做 30 秒正式测速
4. 对候选节点补做公网出口质量测试
5. 根据体感与测速结果，整理出常用 Exit Node 优先级列表

## 12. 常用命令速查

### 客户端测速

```bash
python3 -m ts_exitbench scan --config config.json --out report.html --speed --duration 5
python3 -m ts_exitbench scan --config config.json --out report.html --speed --duration 30
```

### Ubuntu 新节点安装

```bash
sudo apt update
sudo apt install -y git python3
git clone https://github.com/Norton-xia-hub/ts-exitbench.git
cd ts-exitbench
git checkout v0.1.1
sudo TS_EXITBENCH_TOKEN='K3T_e05o2Fj7NUpzgVUcY4XttRdQ5Bo64B0ftqFnDTs' ./install-agent.sh
```

### 节点验收

```bash
sudo systemctl status ts-exitbench-agent
ss -lntp | grep 51234
tailscale ip -4
sudo cat /etc/ts-exitbench/config.json
```

### 出口质量测试

```bash
curl ip.sb
curl -I https://www.google.com
curl -I https://chatgpt.com
curl -I https://www.youtube.com
curl https://ipinfo.io
```
