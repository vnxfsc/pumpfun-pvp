class Mode(Enum):
    WAITING = 0
    AUTO = 1
    MANUAL = 2

# 全局控制标志
should_exit = False
current_mode = Mode.WAITING
input_thread = None
mint_address = None
wallets = None
analyzer = None
my_wallets = set()

# 全局配置
config = {
    "main_wallet_key": None,
    "min_amount": None,
    "max_amount": None,
    "pump_amount": None
}

def signal_handler(signum, frame):
    """处理Ctrl+C信号"""
    global should_exit
    print("\n正在安全退出程序...")
    should_exit = True

def print_menu():
    """打印操作菜单"""
    print("\n=== 操作菜单 ===")
    print("1: 全自动模式 (自动执行所有步骤)")
    print("2: 创建代币 (执行捆绑买入)")
    print("3: 执行一次拉盘")
    print("4: 全部卖出")
    print("q: 退出程序")
    print("-" * 50)

def input_handler():
    """处理用户输入的线程"""
    global should_exit, current_mode, mint_address, wallets, analyzer, my_wallets
    
    while not should_exit:
        try:
            cmd = input().lower()
            if cmd == '1':  # 全自动模式
                print("\n切换到全自动模式...")
                asyncio.create_task(auto_mode())
            
            elif cmd == '2':  # 创建代币
                print("\n开始创建代币...")
                asyncio.create_task(create_and_buy())
            
            elif cmd == '3':  # 执行一次拉盘
                if mint_address:
                    print("\n执行一次拉盘...")
                    asyncio.create_task(pump_token(mint_address, config["pump_amount"], config["main_wallet_key"]))
                else:
                    print("\n请先创建代币")
            
            elif cmd == '4':  # 全部卖出
                if mint_address:
                    print("\n开始全部卖出...")
                    asyncio.create_task(sell_token(mint_address))
                else:
                    print("\n请先创建代币")
            
            elif cmd == 'q':  # 退出程序
                print("\n准备退出程序...")
                should_exit = True
                break
            
            print_menu()  # 每次操作后重新打印菜单

        except EOFError:
            break

async def setup_wallets():
    """创建和初始化钱包"""
    global wallets, my_wallets
    print("1. 开始创建钱包...")
    wallets = create_wallets(15)  # 创建15个钱包
    
    print("\n2. 开始分发资金...")
    transfer = WalletTransfer(config["main_wallet_key"])
    success = await transfer.distribute_initial_funds(config["min_amount"], config["max_amount"])
    if not success:
        print("分发资金失败")
        return False
    
    my_wallets = set(w["public_key"] for w in wallets)
    return True
