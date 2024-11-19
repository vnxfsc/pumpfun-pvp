import asyncio
from src.websockets.subscribe_new import get_new_token_data
from src.pump.create import create_token
from src.pump.trade import pump_token, sell_token
from src.websockets.subscribe_token import ProgramAnalyzer
from src.wallet.create_wallet import create_wallets, archive_wallets
from src.wallet.transfer import WalletTransfer
import time
import random
import threading
import sys
import signal
from enum import Enum
from solders.keypair import Keypair

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

async def create_and_buy():
    """创建代币并执行捆绑买入"""
    global mint_address, analyzer
    
    # 获取新代币数据
    print("\n等待新代币数据...")
    token_data = await get_new_token_data()
    if not token_data or not token_data['ipfs_data']:
        print("获取IPFS数据失败")
        return False

    # 创建代币
    print("\n开始创建代币...")
    mint_address = await create_token(token_data['ipfs_data'], config["min_amount"], config["max_amount"])
    if not mint_address:
        print("创建代币失败")
        return False

    # 创建分析器
    analyzer = ProgramAnalyzer(mint_address)
    return True

async def auto_mode():
    """全自动模式"""
    global mint_address, analyzer, wallets, my_wallets

    # 1. 设置钱包
    if not wallets:
        if not await setup_wallets():
            return

    # 2. 创建代币
    if not await create_and_buy():
        return

    # 3. 监控并自动拉盘
    print(f"\n开始监控代币: {mint_address}")
    no_trade_time = time.time()
    
    while not should_exit:
        stats = await analyzer.get_current_stats()
        current_time = time.time()
        
        # 排除我们的钱包后的交易统计
        filtered_stats = {
            k: v for k, v in stats["stats"].items() 
            if k not in my_wallets
        }
        
        # 检查是否需要拉盘
        if not filtered_stats:  # 如果没有外部交易
            if current_time - no_trade_time > 30:  # 30秒无人交易就拉盘
                await pump_token(mint_address, config["pump_amount"], config["main_wallet_key"])
                no_trade_time = current_time
        else:
            no_trade_time = current_time

        # 检查卖出条件
        profit = sum(v["total_buy_sol"] - v["total_sell_sol"] for v in filtered_stats.values())
        if (profit > 5 or  # 买入比卖出多5 SOL
            stats["progress"] > 70 or  # 进度超过70%
            current_time - stats["start_time"] > 240):  # 开盘超过4分钟
            
            # 执行卖出
            print("\n满足卖出条件，开始卖出...")
            sell_success = await sell_token(mint_address)
            
            if sell_success:
                # 归集资金
                print("\n开始归集资金...")
                transfer = WalletTransfer(config["main_wallet_key"])
                if await transfer.collect_all_funds():
                    # 只有在归集成功后才归档钱包
                    archive_wallets()
                    print("已归档使用过的钱包")
            break

        await asyncio.sleep(1)

async def verify_main_wallet(private_key):
    """验证主钱包私钥并显示信息"""
    try:
        # 检查私钥格式
        if len(private_key) < 80:  # base58编码的私钥通常大于80个字符
            print("错误: 私钥格式不正确")
            return False

        # 创建钱包对象
        try:
            wallet = Keypair.from_base58_string(private_key)
        except Exception as e:
            print("错误: 无效的私钥格式")
            return False
        
        # 创建转账对象来使用其获取余额的方法
        transfer = WalletTransfer(private_key)
        
        try:
            # 获取余额
            balance = await transfer.get_balance(str(wallet.pubkey()))
            
            print("\n=== 主钱包信息 ===")
            print(f"地址: {wallet.pubkey()}")
            print(f"当前余额: {balance/1e9:.4f} SOL")
            print("-" * 50)
            
            # 检查余额是否足够
            if balance < 1e9:  # 小于1 SOL
                print("警告: 钱包余额过低，可能无法完成操作")
                return False
                
            return True
            
        except Exception as e:
            print(f"错误: 无法获取钱包余额，请检查网络连接")
            return False
        
    except Exception as e:
        print(f"验证主钱包失败: {str(e)}")
        return False

async def monitor_and_pump(analyzer, wallets, pump_amount, my_wallets):
    """监控交易并在需要时拉盘"""
    global should_exit, config
    no_trade_time = time.time()
    last_pump_time = time.time()
    
    try:
        while not should_exit:
            try:
                stats = await analyzer.get_current_stats()
                current_time = time.time()
                
                # 排除我们的钱包后的交易统计
                filtered_stats = {
                    k: v for k, v in stats["stats"].items() 
                    if k not in my_wallets
                }
                
                # 打印实时状态
                time_elapsed = current_time - stats["start_time"]
                profit = sum(v["total_buy_sol"] - v["total_sell_sol"] for v in filtered_stats.values())
                print(f"\r当前状态 - 差价: {profit:.2f} SOL | 进度: {stats['progress']:.1f}% | 运行时间: {time_elapsed:.0f}秒 | 距离上次拉盘: {current_time - last_pump_time:.0f}秒", end='', flush=True)
                
                # 检查是否需要拉盘
                if not filtered_stats:  # 如果没有外部交易
                    if current_time - no_trade_time > 30:  # 30秒无人交易就拉盘
                        if current_time - last_pump_time > 30:  # 确保两次拉盘间隔至少30秒
                            print("\n\n开始执行拉盘...")
                            success = await pump_token(mint_address, pump_amount, config["main_wallet_key"])
                            if success:
                                last_pump_time = current_time
                                print("拉盘完成")
                            else:
                                print("拉盘失败")
                        no_trade_time = current_time
                else:
                    no_trade_time = current_time

                # 检查卖出条件
                if (profit > 5 or  # 买入比卖出多5 SOL
                    stats["progress"] > 70 or  # 进度超过70%
                    time_elapsed > 240):  # 开盘超过4分钟
                    
                    print("\n\n满足卖出条件:")
                    if profit > 5:
                        print("- 差价超过5 SOL")
                    if stats["progress"] > 70:
                        print("- 进度超过70%")
                    if time_elapsed > 240:
                        print("- 开盘时间超过4分钟")
                    
                    print("\n开始卖出...")
                    sell_success = await sell_token(mint_address)
                    
                    if sell_success:
                        print("\n等待10秒确保卖出交易完成...")
                        await asyncio.sleep(10)
                        
                        print("\n开始归集资金...")
                        transfer = WalletTransfer(config["main_wallet_key"])
                        if await transfer.collect_all_funds():
                            archive_wallets()
                            print("已归档使用过的钱包")
                        else:
                            print("归集资金失败")
                    else:
                        print("卖出失败")
                    break

                await asyncio.sleep(1)
                
            except Exception as e:
                print(f"\n监控错误: {e}")
                await asyncio.sleep(1)
                
    except asyncio.CancelledError:
        print("\n监控任务被取消")
    except Exception as e:
        print(f"\n监控任务发生错误: {e}")

async def main():
    global input_thread, should_exit, config
    try:
        # 设置信号处理
        signal.signal(signal.SIGINT, signal_handler)
        
        # 获取并验证主钱包私钥
        while True:
            try:
                print("请输入主钱包私钥 (Ctrl+C退出): ", end='', flush=True)
                config["main_wallet_key"] = input()
                if await verify_main_wallet(config["main_wallet_key"]):
                    break
                print("请重新输入私钥")
            except (KeyboardInterrupt, EOFError):
                print("\n程序已退出")
                return
        
        # 获取其他配置
        while True:
            try:
                print("请输入最小SOL金额 (Ctrl+C退出): ", end='', flush=True)
                config["min_amount"] = float(input())
                if config["min_amount"] > 0:
                    break
                print("金额必须大于0")
            except ValueError:
                print("请输入有效的数字")
            except (KeyboardInterrupt, EOFError):
                print("\n程序已退出")
                return

        while True:
            try:
                print("请输入最大SOL金额 (Ctrl+C退出): ", end='', flush=True)
                config["max_amount"] = float(input())
                if config["max_amount"] > config["min_amount"]:
                    break
                print("最大金额必须大于最小金额")
            except ValueError:
                print("请输入有效的数字")
            except (KeyboardInterrupt, EOFError):
                print("\n程序已退出")
                return

        while True:
            try:
                print("请输入每次拉盘总SOL金额 (Ctrl+C退出): ", end='', flush=True)
                config["pump_amount"] = float(input())
                if config["pump_amount"] > 0:
                    break
                print("金额必须大于0")
            except ValueError:
                print("请输入有效的数字")
            except (KeyboardInterrupt, EOFError):
                print("\n程序已退出")
                return

        # 打印菜单
        print_menu()

        # 启动输入处理线程
        input_thread = threading.Thread(target=input_handler, daemon=True)
        input_thread.start()

        # 保持主线程运行
        while not should_exit:
            await asyncio.sleep(1)

    except KeyboardInterrupt:
        print("\n程序已停止")
    except Exception as e:
        print(f"发生错误: {e}")
    finally:
        should_exit = True
        if input_thread and input_thread.is_alive():
            input_thread.join(timeout=1)

if __name__ == "__main__":
    asyncio.run(main())
