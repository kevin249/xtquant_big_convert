"""Big QMT market data adapter.

This module only wraps ContextInfo. It does not make trading decisions.
"""

from ..code_utils import normalize_stock_code


MARKET_CODES = {"SH", "SZ", "BJ", "HK"}


def normalize_market_or_stock_code(code):
    text = str(code or "").strip().upper()
    if text in MARKET_CODES:
        return text
    return normalize_stock_code(text)


class BigQmtMarketDataProvider:
    def __init__(self, context_info):
        self.context_info = context_info

    def _context_method(self, method_name):
        method = getattr(self.context_info, method_name, None)
        if method is None:
            raise NotImplementedError("ContextInfo.%s is not available" % method_name)
        return method

    def _call_context(self, method_name, *args, **kwargs):
        return self._context_method(method_name)(*args, **kwargs)

    def _call_first_supported(self, shapes):
        last_error = None
        for method_name, args, kwargs in shapes:
            method = getattr(self.context_info, method_name, None)
            if method is None:
                continue
            try:
                return method(*args, **kwargs)
            except TypeError as exc:
                last_error = exc
                continue
        if last_error is not None:
            raise last_error
        raise NotImplementedError("none of the ContextInfo methods is available")

    def _market_data_shapes(self, method_name, **params):
        field_list = list(params.get("field_list") or params.get("fields") or [])
        stock_list = list(params.get("stock_list") or params.get("stock_code") or [])
        period = params.get("period", "1d")
        start_time = params.get("start_time", "")
        end_time = params.get("end_time", "")
        count = params.get("count", -1)
        dividend_type = params.get("dividend_type", "none")
        fill_data = params.get("fill_data", True)
        data_dir = params.get("data_dir")

        mini_kwargs = {
            "field_list": field_list,
            "stock_list": stock_list,
            "period": period,
            "start_time": start_time,
            "end_time": end_time,
            "count": count,
            "dividend_type": dividend_type,
            "fill_data": fill_data,
        }
        big_kwargs = {
            "fields": field_list,
            "stock_code": stock_list,
            "period": period,
            "start_time": start_time,
            "end_time": end_time,
            "count": count,
            "dividend_type": dividend_type,
        }
        if method_name == "get_local_data" and data_dir is not None:
            mini_kwargs["data_dir"] = data_dir
            big_kwargs["data_dir"] = data_dir
        positional_tail_kwargs = {
            "period": period,
            "start_time": start_time,
            "end_time": end_time,
            "count": count,
            "dividend_type": dividend_type,
        }
        if method_name == "get_local_data" and data_dir is not None:
            positional_tail_kwargs["data_dir"] = data_dir

        return [
            (method_name, (), big_kwargs),
            (method_name, (), mini_kwargs),
            (
                method_name,
                (field_list, stock_list, period, start_time, end_time, count, dividend_type, fill_data),
                {},
            ),
            (method_name, (field_list, stock_list), positional_tail_kwargs),
            (
                method_name,
                (field_list,),
                {
                    "stock_code": stock_list,
                    "period": period,
                    "start_time": start_time,
                    "end_time": end_time,
                    "count": count,
                    "dividend_type": dividend_type,
                },
            ),
            (
                method_name,
                (field_list,),
                {
                    "stock_list": stock_list,
                    "period": period,
                    "start_time": start_time,
                    "end_time": end_time,
                    "count": count,
                    "dividend_type": dividend_type,
                    "fill_data": fill_data,
                },
            ),
        ]

    def get_ticks(self, codes):
        normalized_codes = [normalize_market_or_stock_code(code) for code in codes]
        data = self.context_info.get_full_tick(normalized_codes)
        return data or {}

    def get_instrument(self, code):
        normalized = normalize_stock_code(code)
        data = self.context_info.get_instrumentdetail(normalized)
        return data or {}

    def get_instrument_type(self, code, variety_list=None):
        if hasattr(self.context_info, "get_instrument_type"):
            return self.context_info.get_instrument_type(code, variety_list)
        normalized = normalize_stock_code(code)
        pure = normalized.split(".")[0]
        result = {
            "stock": pure.startswith(("000", "001", "002", "003", "300", "301", "600", "601", "603", "605", "688", "689")),
            "fund": pure.startswith(("15", "16", "50", "51", "56", "58")),
            "etf": pure.startswith(("15", "51", "56", "58")),
            "bond": pure.startswith(("11", "12")),
            "index": pure.startswith(("000", "399")) and not normalized.startswith(("000001.SZ", "000002.SZ")),
        }
        if variety_list:
            return {str(name): bool(result.get(str(name), False)) for name in variety_list}
        return result

    def get_stock_list_in_sector(self, sector_name, real_timetag=-1):
        shapes = [
            ("get_stock_list_in_sector", (sector_name, real_timetag), {}),
            ("get_stock_list_in_sector", (sector_name,), {}),
        ]
        data = self._call_first_supported(shapes)
        return data or []

    def get_market_data(
        self,
        field_list=None,
        stock_list=None,
        period="1d",
        start_time="",
        end_time="",
        count=-1,
        dividend_type="none",
        fill_data=True,
    ):
        return self._call_first_supported(
            self._market_data_shapes(
                "get_market_data",
                field_list=field_list,
                stock_list=stock_list,
                period=period,
                start_time=start_time,
                end_time=end_time,
                count=count,
                dividend_type=dividend_type,
                fill_data=fill_data,
            )
        )

    def get_market_data_ex(self, **kwargs):
        shapes = self._market_data_shapes("get_market_data_ex", **kwargs)
        if hasattr(self.context_info, "get_market_data"):
            shapes.extend(self._market_data_shapes("get_market_data", **kwargs))
        return self._call_first_supported(shapes)

    def get_local_data(self, **kwargs):
        shapes = self._market_data_shapes("get_local_data", **kwargs)
        if hasattr(self.context_info, "get_market_data"):
            shapes.extend(self._market_data_shapes("get_market_data", **kwargs))
        return self._call_first_supported(shapes)

    def get_divid_factors(self, stock_code, start_time="", end_time=""):
        return self._call_context("get_divid_factors", stock_code, start_time, end_time)

    def download_history_data(self, stock_code, period, start_time="", end_time="", incrementally=None):
        kwargs = {"stock_code": stock_code, "period": period, "start_time": start_time, "end_time": end_time}
        if incrementally is not None:
            kwargs["incrementally"] = incrementally
        return self._call_context("download_history_data", **kwargs)

    def download_history_data2(self, stock_list, period, start_time="", end_time="", incrementally=None):
        kwargs = {"stock_list": stock_list, "period": period, "start_time": start_time, "end_time": end_time}
        if incrementally is not None:
            kwargs["incrementally"] = incrementally
        return self._call_context("download_history_data2", **kwargs)

    def get_trading_dates(self, market, start_time="", end_time="", count=-1):
        return self._call_context("get_trading_dates", market, start_time, end_time, count)

    def get_holidays(self):
        return self._call_context("get_holidays")

    def download_holiday_data(self, incrementally=True):
        return self._call_context("download_holiday_data", incrementally=incrementally)

    def get_ipo_info(self, start_time="", end_time=""):
        return self._call_context("get_ipo_info", start_time, end_time)

    def get_etf_info(self):
        return self._call_context("get_etf_info")

    def download_etf_info(self):
        return self._call_context("download_etf_info")

    def get_option_list(self, undl_code, dedate, opttype="", isavailavle=False):
        return self._call_context("get_option_list", undl_code, dedate, opttype, isavailavle)

    def get_his_option_list(self, undl_code, dedate):
        return self._call_context("get_his_option_list", undl_code, dedate)

    def get_his_option_list_batch(self, undl_code, start_time="", end_time=""):
        return self._call_context("get_his_option_list_batch", undl_code, start_time, end_time)

    def get_financial_data(self, stock_list, table_list=None, start_time="", end_time="", report_type="report_time"):
        return self._call_context(
            "get_financial_data",
            stock_list,
            table_list or [],
            start_time,
            end_time,
            report_type,
        )

    def download_financial_data(self, stock_list, table_list=None, start_time="", end_time="", incrementally=None):
        kwargs = {
            "stock_list": stock_list,
            "table_list": table_list or [],
            "start_time": start_time,
            "end_time": end_time,
        }
        if incrementally is not None:
            kwargs["incrementally"] = incrementally
        return self._call_context("download_financial_data", **kwargs)

    def download_financial_data2(self, stock_list, table_list=None, start_time="", end_time=""):
        return self._call_context("download_financial_data2", stock_list, table_list or [], start_time, end_time)

    def get_sector_list(self):
        return self._call_context("get_sector_list")

    def get_sector_info(self, sector_name=""):
        return self._call_context("get_sector_info", sector_name)

    def get_markets(self):
        return self._call_context("get_markets")

    def get_market_last_trade_date(self, market):
        return self._call_context("get_market_last_trade_date", market)

    def call_formula(self, formula_name, stock_code, period, start_time="", end_time="", count=-1, dividend_type=None, extend_param=None):
        return self._call_context(
            "call_formula",
            formula_name,
            stock_code,
            period,
            start_time,
            end_time,
            count,
            dividend_type,
            extend_param or {},
        )

    def subscribe_formula(self, formula_name, stock_code, period, start_time="", end_time="", count=-1, dividend_type=None, extend_param=None):
        return self._call_context(
            "subscribe_formula",
            formula_name,
            stock_code,
            period,
            start_time,
            end_time,
            count,
            dividend_type,
            extend_param or {},
        )

    def unsubscribe_formula(self, request_id):
        return self._call_context("unsubscribe_formula", request_id)

    def get_formula_result(self, request_id, start_time="", end_time="", count=-1, timeout_second=-1):
        return self._call_context("get_formula_result", request_id, start_time, end_time, count, timeout_second)

    def gen_factor_index(self, data_name, formula_name, vars, sector_list, start_time="", end_time="", period="1d", dividend_type="none"):
        return self._call_context(
            "gen_factor_index",
            data_name,
            formula_name,
            vars,
            sector_list,
            start_time,
            end_time,
            period,
            dividend_type,
        )
