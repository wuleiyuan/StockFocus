import argparse
import sys
import logging
from typing import Dict, Any, Optional

logger = logging.getLogger(__name__)


class CLIArgs:
    _instance = None
    _args: Optional[argparse.Namespace] = None
    
    def __new__(cls):
        if cls._instance is None:
            cls._instance = super().__new__(cls)
        return cls._instance
    
    @staticmethod
    def parse():
        if CLIArgs._args is None:
            parser = argparse.ArgumentParser(
                prog='stockfocus',
                description='StockFocus Pro - 量化投研系统',
                formatter_class=argparse.RawDescriptionHelpFormatter,
                epilog="""
示例用法:
  python main.py scan --roe-threshold 18 --max-stocks 100
  python main.py backend --refresh-interval 5
  python main.py etl --continuous --interval 60
  python main.py web --debug
                """
            )
            
            parser.add_argument(
                '--mode', 
                choices=['scan', 'backend', 'web', 'etl', 'etl-pipeline'],
                default='web',
                help='运行模式 (默认: web)'
            )
            
            parser.add_argument(
                '--roe-threshold',
                type=float,
                default=15.0,
                help='ROE筛选阈值 (默认: 15.0)'
            )
            
            parser.add_argument(
                '--years',
                type=int,
                default=10,
                help='ROE分析年数 (默认: 10)'
            )
            
            parser.add_argument(
                '--max-stocks',
                type=int,
                default=200,
                help='最大扫描股票数 (默认: 200)'
            )
            
            parser.add_argument(
                '--batch-size',
                type=int,
                default=50,
                help='批量处理大小 (默认: 50)'
            )
            
            parser.add_argument(
                '--refresh-interval',
                type=int,
                default=10,
                help='刷新间隔秒数 (默认: 10)'
            )
            
            parser.add_argument(
                '--interval',
                type=int,
                default=60,
                help='ETL循环间隔秒数 (默认: 60)'
            )
            
            parser.add_argument(
                '--continuous',
                action='store_true',
                help='ETL持续运行模式'
            )
            
            parser.add_argument(
                '--max-iterations',
                type=int,
                help='ETL最大迭代次数 (默认: 无限)'
            )
            
            parser.add_argument(
                '--symbols',
                type=str,
                help='指定股票代码,逗号分隔 (如: 600519,000858)'
            )
            
            parser.add_argument(
                '--debug',
                action='store_true',
                help='启用调试模式'
            )
            
            parser.add_argument(
                '--skip-scan',
                action='store_true',
                help='Web模式: 跳过初始扫描'
            )
            
            parser.add_argument(
                '--log-level',
                choices=['DEBUG', 'INFO', 'WARNING', 'ERROR'],
                default='INFO',
                help='日志级别 (默认: INFO)'
            )
            
            CLIArgs._args = parser.parse_args()
        
        return CLIArgs._args
    
    @classmethod
    def get(cls, key: str, default: Any = None) -> Any:
        args = cls.parse()
        return getattr(args, key, default)
    
    @classmethod
    def get_all(cls) -> Dict[str, Any]:
        args = cls.parse()
        return vars(args)


def get_args() -> argparse.Namespace:
    return CLIArgs.parse()


def setup_logging(level: str):
    logging.basicConfig(
        level=getattr(logging, level.upper()),
        format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
    )


def print_banner():
    print("""
╔═══════════════════════════════════════════════════╗
║         StockFocus Pro 量化投研系统             ║
║         Dynamic Valuation + Multi-Factor        ║
╚═══════════════════════════════════════════════════╝
    """)


def main():
    args = get_args()
    setup_logging(args.log_level)
    
    if args.debug:
        logger.setLevel(logging.DEBUG)
        print(f"[DEBUG] 运行参数: {args}")
    
    if args.mode == 'scan':
        print_banner()
        print(f"🔍 启动股票扫描器 (ROE >= {args.roe_threshold}%, 年数: {args.years})")
        from stock_scanner import StockScanner
        scanner = StockScanner()
        scanner.run_full_scan(
            roe_threshold=args.roe_threshold,
            years=args.years,
            max_stocks=args.max_stocks
        )
        
    elif args.mode == 'backend':
        print_banner()
        print(f"🚀 启动后端数据服务 (刷新间隔: {args.refresh_interval}秒)")
        from backend_service import StockDataService
        service = StockDataService()
        service.update_stock_prices_loop()
        
    elif args.mode == 'etl':
        print_banner()
        print(f"🔄 启动ETL处理器")
        from backend_etl import ETLProcessor
        processor = ETLProcessor()
        processor.run_etl_loop()
        
    elif args.mode == 'etl-pipeline':
        print_banner()
        print(f"🔄 启动专业ETL管道")
        from etl_pipeline import ETLScheduler
        
        symbols = None
        if args.symbols:
            symbols = [s.strip() for s in args.symbols.split(',')]
        
        scheduler = ETLScheduler()
        scheduler.add_price_etl(symbols)
        
        if args.continuous:
            print(f"持续运行模式 (间隔: {args.interval}秒, 最大迭代: {args.max_iterations or '无限'})")
            scheduler.run_continuous(
                interval_seconds=args.interval,
                max_iterations=args.max_iterations
            )
        else:
            results = scheduler.run_once()
            for r in results:
                print(f"状态: {r.status.value}, 成功: {r.success_records}/{r.total_records}")
        
    elif args.mode == 'web':
        print_banner()
        print("🌐 启动Web界面")
        import streamlit.web.cli as stcli
        sys.argv = ['streamlit', 'run', 'app_web.py', 
                    '--server.port=8501', 
                    '--server.address=0.0.0.0']
        if args.debug:
            sys.argv.append('--logger.level=debug')
        stcli.main()


if __name__ == "__main__":
    main()
