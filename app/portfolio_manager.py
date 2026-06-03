import os
import json
import math
from typing import Dict, List, Any, Optional, Literal, TypedDict
from app.utils.logger import setup_logger

logger = setup_logger("portfolio_manager", "logs/app.log")

class HoldingEvaluation(TypedDict):
    symbol: str
    name: str
    asset_class: str
    quantity: float
    purchase_value: float
    current_price: float
    current_value: float
    unrealized_pnl: float
    actual_weight: float

class RebalanceTransaction(TypedDict):
    symbol: str
    name: str
    asset_class: str
    current_qty: float
    current_value: float
    target_value: float
    difference: float
    action: Literal["BUY", "SELL", "HOLD"]
    suggested_qty_delta: float

class PortfolioEvaluation(TypedDict):
    total_value: float
    holdings_eval: list[HoldingEvaluation]
    rebalance_actions: list[RebalanceTransaction]
    rebalance_triggered: bool

class PortfolioManager:
    """
    Manages local portfolio configurations and executes logic to balance portfolios
    to targeted weights.
    """

    def __init__(self, portfolio_path: str) -> None:
        """
        Args:
            portfolio_path: Path to the portfolio JSON file.
        """
        self.path = portfolio_path

    def load_portfolio(self) -> Dict[str, Any]:
        """
        Reads local portfolio JSON configuration and performs basic validation.
        
        Returns:
            Dictionary representing portfolio contents.
            
        Raises:
            FileNotFoundError: If the portfolio file does not exist.
            ValueError: If the portfolio file is invalid JSON or violates schema constraints.
        """
        logger.info(f"Loading portfolio from: {self.path}")
        if not os.path.exists(self.path):
            logger.error(f"Portfolio file not found at {self.path}")
            raise FileNotFoundError(f"Portfolio configuration file not found: {self.path}")

        try:
            with open(self.path, "r", encoding="utf-8") as f:
                data = json.load(f)
        except json.JSONDecodeError as e:
            logger.error(f"Invalid JSON format in portfolio file: {str(e)}")
            raise ValueError(f"Portfolio file is not a valid JSON: {str(e)}")

        self.validate_portfolio(data)
        return data

    def save_portfolio(self, portfolio_data: Dict[str, Any]) -> None:
        """
        Writes updated portfolio configurations back to local JSON file.
        """
        logger.info(f"Saving portfolio configuration to: {self.path}")
        self.validate_portfolio(portfolio_data)
        try:
            with open(self.path, "w", encoding="utf-8") as f:
                json.dump(portfolio_data, f, indent=2, ensure_ascii=False)
            logger.info("Portfolio saved successfully.")
        except Exception as e:
            logger.error(f"Failed to save portfolio configuration: {str(e)}")
            raise e

    def validate_portfolio(self, data: Dict[str, Any]) -> None:
        """
        Validates the portfolio structure and allocation weights.
        """
        # 1. Required Top Level Fields
        required_fields = ["cash", "holdings", "target_allocation"]
        for field in required_fields:
            if field not in data:
                raise ValueError(f"Missing required portfolio property: '{field}'")

        # 2. Check types
        if not isinstance(data["cash"], (int, float)) or data["cash"] < 0:
            raise ValueError("Property 'cash' must be a non-negative number.")
        if not isinstance(data["holdings"], list):
            raise ValueError("Property 'holdings' must be an array.")
        if not isinstance(data["target_allocation"], dict):
            raise ValueError("Property 'target_allocation' must be an object.")

        # 3. Validate holdings items
        for idx, holding in enumerate(data["holdings"]):
            holding_required = ["symbol", "name", "quantity", "purchase_price", "asset_class"]
            for field in holding_required:
                if field not in holding:
                    raise ValueError(f"Holding item {idx} is missing required property '{field}'")
            
            if holding["asset_class"] not in ["stock", "bond", "commodity", "cash"]:
                raise ValueError(f"Holding item {idx} has invalid asset_class: '{holding['asset_class']}'")
            if holding["quantity"] < 0:
                raise ValueError(f"Holding item {idx} has negative quantity: {holding['quantity']}")
            if holding["purchase_price"] < 0:
                raise ValueError(f"Holding item {idx} has negative purchase_price: {holding['purchase_price']}")

        # 4. Target Allocation weights check (must sum to 1.0)
        allocation = data["target_allocation"]
        required_classes = ["stock", "bond", "commodity", "cash"]
        for c in required_classes:
            if c not in allocation:
                raise ValueError(f"target_allocation is missing target weight for class: '{c}'")
            if not isinstance(allocation[c], (int, float)) or not (0.0 <= allocation[c] <= 1.0):
                raise ValueError(f"Allocation weight for '{c}' must be between 0.0 and 1.0.")

        total_weight = sum(allocation[c] for c in required_classes)
        if not math.isclose(total_weight, 1.0, rel_tol=1e-5):
            raise ValueError(f"Portfolio target allocation weights must sum to 1.0, got: {total_weight}")

    def _get_asset_currency(self, symbol: str) -> Literal["KRW", "USD"]:
        """Infers native currency of the asset based on the ticker symbol."""
        if symbol.endswith(".KS") or symbol.endswith(".KQ") or (symbol.isdigit() and len(symbol) == 6):
            return "KRW"
        if symbol in ["^KS11", "^KQ11"]:
            return "KRW"
        return "USD"

    def evaluate_and_rebalance(
        self, 
        current_prices: Dict[str, float], 
        recommended_stocks: Optional[List[str]] = None
    ) -> PortfolioEvaluation:
        """
        Calculates current portfolio weights, compares them against target weights,
        and generates transaction logs required to align weights.
        
        Args:
            current_prices: Real-time price dictionary for active symbols.
            recommended_stocks: Optional list of tickers recommended for purchase.
            
        Returns:
            Aggregated PortfolioEvaluation details.
        """
        portfolio = self.load_portfolio()
        base_currency = portfolio.get("base_currency", "KRW")
        cash_base = float(portfolio["cash"])
        
        # Determine exchange rate USD/KRW
        er = current_prices.get("USDKRW=X") or current_prices.get("USD_KRW") or current_prices.get("KRW=X") or 1350.0
        logger.info(f"Using USD/KRW exchange rate: {er}")

        holdings_eval: List[HoldingEvaluation] = []
        total_holdings_value = 0.0

        # Step 1: Calculate current valuation of each asset in base currency
        for holding in portfolio["holdings"]:
            symbol = holding["symbol"]
            qty = float(holding["quantity"])
            purchase_price = float(holding["purchase_price"])
            asset_class = holding["asset_class"]
            
            # Fetch current native price
            price_native = current_prices.get(symbol)
            if price_native is None:
                logger.warning(f"Current price for {symbol} not found in input. Falling back to purchase price.")
                price_native = purchase_price

            asset_currency = self._get_asset_currency(symbol)
            
            # Convert current price and purchase price to base currency
            if asset_currency == "USD" and base_currency == "KRW":
                price_base = price_native * er
                purchase_price_base = purchase_price * er
            elif asset_currency == "KRW" and base_currency == "USD":
                price_base = price_native / er
                purchase_price_base = purchase_price / er
            else:
                price_base = price_native
                purchase_price_base = purchase_price

            current_value = qty * price_base
            purchase_value = qty * purchase_price_base
            unrealized_pnl = current_value - purchase_value
            total_holdings_value += current_value

            holdings_eval.append({
                "symbol": symbol,
                "name": holding["name"],
                "asset_class": asset_class,
                "quantity": qty,
                "purchase_value": purchase_value,
                "current_price": price_native,
                "current_value": current_value,
                "unrealized_pnl": unrealized_pnl,
                "actual_weight": 0.0 # Filled in Step 2
            })

        # Portfolio total valuation (including cash)
        total_portfolio_value = total_holdings_value + cash_base
        logger.info(f"Total Portfolio Value: {total_portfolio_value:.2f} {base_currency}")

        # Step 2: Compute actual weights
        class_values = {"stock": 0.0, "bond": 0.0, "commodity": 0.0, "cash": cash_base}
        for h_eval in holdings_eval:
            h_eval["actual_weight"] = h_eval["current_value"] / total_portfolio_value if total_portfolio_value > 0 else 0.0
            class_values[h_eval["asset_class"]] += h_eval["current_value"]

        # Step 3: Check drift and trigger rebalancing
        target_allocation = portfolio["target_allocation"]
        drift_detected = False
        rebalance_trigger_threshold = 0.05

        class_deviations = {}
        for c in ["stock", "bond", "commodity", "cash"]:
            actual_w = class_values[c] / total_portfolio_value if total_portfolio_value > 0 else 0.0
            target_w = float(target_allocation[c])
            deviation = actual_w - target_w
            class_deviations[c] = deviation
            if abs(deviation) > rebalance_trigger_threshold:
                drift_detected = True
                logger.info(f"Rebalance triggered by class '{c}': Drift is {deviation*100:.2f}% (Limit: 5%)")

        transactions: List[RebalanceTransaction] = []

        # If rebalancing is triggered, generate detailed recommendations
        if drift_detected:
            # Phase A: Overweighted Classes (Sell)
            sell_actions: List[Dict[str, Any]] = []
            for c in ["stock", "bond", "commodity"]:
                deviation = class_deviations[c]
                if deviation > 0: # Overweighted
                    class_value = class_values[c]
                    target_value = total_portfolio_value * target_allocation[c]
                    excess_value_base = class_value - target_value
                    
                    # Distribute sell order proportionally to holdings in this class
                    class_holdings = [h for h in holdings_eval if h["asset_class"] == c]
                    for h in class_holdings:
                        share_of_class = h["current_value"] / class_value if class_value > 0 else 0
                        sell_val_base = excess_value_base * share_of_class
                        
                        # Convert back to native currency price
                        asset_currency = self._get_asset_currency(h["symbol"])
                        if asset_currency == "USD" and base_currency == "KRW":
                            sell_val_native = sell_val_base / er
                        elif asset_currency == "KRW" and base_currency == "USD":
                            sell_val_native = sell_val_base * er
                        else:
                            sell_val_native = sell_val_base

                        qty_to_sell = sell_val_native / h["current_price"] if h["current_price"] > 0 else 0
                        qty_to_sell_rounded = int(math.floor(qty_to_sell))
                        
                        if qty_to_sell_rounded > 0:
                            sell_actions.append({
                                "symbol": h["symbol"],
                                "name": h["name"],
                                "asset_class": c,
                                "current_qty": h["quantity"],
                                "current_value": h["current_value"],
                                "target_value": h["current_value"] - sell_val_base,
                                "difference": -sell_val_base,
                                "action": "SELL",
                                "suggested_qty_delta": float(-qty_to_sell_rounded)
                            })

            # Phase B: Underweighted Classes (Buy)
            buy_actions: List[Dict[str, Any]] = []
            for c in ["stock", "bond", "commodity"]:
                deviation = class_deviations[c]
                if deviation < 0: # Underweighted
                    deficit_value_base = abs(deviation) * total_portfolio_value
                    
                    # Identify buy targets
                    target_symbols = []
                    if c == "stock":
                        # Use recommended stocks first
                        if recommended_stocks:
                            target_symbols = [s for s in recommended_stocks]
                        else:
                            # Fallback to existing stock holdings
                            target_symbols = [h["symbol"] for h in holdings_eval if h["asset_class"] == "stock"]
                    elif c == "bond":
                        target_symbols = [h["symbol"] for h in holdings_eval if h["asset_class"] == "bond"]
                        # If no holdings, use default bond ETF
                        if not target_symbols:
                            target_symbols = ["TLT"]
                    elif c == "commodity":
                        target_symbols = [h["symbol"] for h in holdings_eval if h["asset_class"] == "commodity"]
                        if not target_symbols:
                            target_symbols = ["GLD"]

                    if target_symbols:
                        # Split cash equally among target instruments
                        buy_val_per_target_base = deficit_value_base / len(target_symbols)
                        for symbol in target_symbols:
                            # Retrieve price
                            price_native = current_prices.get(symbol)
                            name = symbol
                            
                            # Try to match name from holdings or default
                            existing_holding = next((h for h in holdings_eval if h["symbol"] == symbol), None)
                            if existing_holding:
                                price_native = existing_holding["current_price"]
                                name = existing_holding["name"]
                            elif price_native is None:
                                price_native = 100.0 # Dummy fallback
                                
                            asset_currency = self._get_asset_currency(symbol)
                            if asset_currency == "USD" and base_currency == "KRW":
                                buy_val_native = buy_val_per_target_base / er
                            elif asset_currency == "KRW" and base_currency == "USD":
                                buy_val_native = buy_val_per_target_base * er
                            else:
                                buy_val_native = buy_val_per_target_base
                                
                            qty_to_buy = buy_val_native / price_native if price_native > 0 else 0
                            qty_to_buy_rounded = int(math.floor(qty_to_buy))
                            
                            current_qty = existing_holding["quantity"] if existing_holding else 0.0
                            current_val = existing_holding["current_value"] if existing_holding else 0.0
                            
                            if qty_to_buy_rounded > 0:
                                buy_actions.append({
                                    "symbol": symbol,
                                    "name": name,
                                    "asset_class": c,
                                    "current_qty": current_qty,
                                    "current_value": current_val,
                                    "target_value": current_val + buy_val_per_target_base,
                                    "difference": buy_val_per_target_base,
                                    "action": "BUY",
                                    "suggested_qty_delta": float(qty_to_buy_rounded)
                                })

            # Combine actions
            transactions.extend(sell_actions)
            transactions.extend(buy_actions)
        else:
            # No transactions required (HOLD for all assets)
            for h in holdings_eval:
                transactions.append({
                    "symbol": h["symbol"],
                    "name": h["name"],
                    "asset_class": h["asset_class"],
                    "current_qty": h["quantity"],
                    "current_value": h["current_value"],
                    "target_value": h["current_value"],
                    "difference": 0.0,
                    "action": "HOLD",
                    "suggested_qty_delta": 0.0
                })

        return {
            "total_value": total_portfolio_value,
            "holdings_eval": holdings_eval,
            "rebalance_actions": transactions,
            "rebalance_triggered": drift_detected
        }
