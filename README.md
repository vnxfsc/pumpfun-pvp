# PumpFun PVP Bot

一个用于 PumpFun 的自动化PVP交易机器人。

## 功能特点

- 自动监控新代币
- 自动创建和分发钱包
- 支持多种操作模式：
  - 全自动模式
  - 手动创建代币
  - 手动拉盘
  - 手动卖出
- 实时监控交易状态
- 智能资金管理
- 自动归集资金

## 安装依赖 

```bash
pip install -r requirements.txt
```
## 目录结构

```
pumpfun-pvp/
├── main.py # 主程序入口
├── wallets/ # 钱包文件目录（自动创建）
├── oldwallets/ # 已使用钱包归档目录
└── src/
├── pump/ # 代币创建和交易相关
│ ├── create.py # 创建代币
│ └── trade.py # 交易操作
├── wallet/ # 钱包管理
│ ├── create_wallet.py # 创建钱包
│ └── transfer.py # 转账操作
└── websockets/ # WebSocket 监控
├── subscribe_new.py # 新代币监控
└── subscribe_token.py # 代币交易监控
```
## 使用说明

1. 启动程序：
```bash
python main.py
```
2. 输入必要参数：
- 主钱包私钥
- 最小 SOL 金额
- 最大 SOL 金额
- 拉盘总 SOL 金额

3. 选择操作模式：
- 1: 全自动模式（自动执行所有步骤）
- 2: 创建代币（执行捆绑买入）
- 3: 执行一次拉盘
- 4: 全部卖出
- q: 退出程序

## 注意事项

1. 确保主钱包有足够的 SOL
2. 所有金额都会自动添加 0.5 SOL 作为手续费
3. 使用 Ctrl+C 可以随时安全退出程序
4. 钱包文件会自动保存和归档
5. 每次拉盘都会创建新的钱包

## 安全建议

1. 不要将私钥保存在代码中
2. 定期清理旧钱包文件
3. 使用完毕后及时归集资金
4. 确保网络环境安全


## 开发说明

- 使用 solders 库进行 Solana 交易
- 使用 websockets 进行实时监控
- 使用 aiohttp 进行异步 HTTP 请求
- 所有关键操作都有重试机制
- 支持自定义配置和错误处理

## 免责声明

本程序仅供学习和研究使用，使用本程序产生的任何后果由使用者自行承担。