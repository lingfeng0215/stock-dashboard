import streamlit as st
import akshare as ak
import pandas as pd
import numpy as np
import plotly.graph_objects as go
import plotly.express as px
from datetime import datetime, timedelta
import streamlit_authenticator as stauth
import yaml
from yaml.loader import SafeLoader
from db import init_db, add_stock, remove_stock, get_watchlist

st.set_page_config(page_title="多股对比看板", layout="wide")

# ========== 配置栏样式 ==========
st.markdown("""
<style>
.st-key-config_sticky {
    position: sticky !important;
    top: 3.5rem !important;
    z-index: 999 !important;
    padding: 8px 12px 4px 12px !important;
    border-radius: 10px !important;
    border: 1px solid rgba(128,128,128,0.25) !important;
    max-height: 75vh !important;
    overflow-y: auto !important;
    box-shadow: 0 2px 8px rgba(0,0,0,0.08) !important;
}
@media (max-width: 768px) {
    .st-key-config_sticky {
        position: relative !important;
        top: auto !important;
        max-height: none !important;
        overflow-y: visible !important;
        padding: 6px 8px 2px 8px !important;
        margin-bottom: 10px !important;
    }
    .st-key-config_sticky h3 { font-size: 16px !important; margin-bottom: 4px !important; }
    .st-key-config_sticky button { font-size: 12px !important; padding: 3px 6px !important; min-height: 28px !important; }
    .st-key-config_sticky label { font-size: 13px !important; }
}
</style>
""", unsafe_allow_html=True)

# ========== Plotly 配置 ==========
PLOTLY_CONFIG = {
    'displayModeBar': True,
    'displaylogo': False,
    'scrollZoom': False,
    'doubleClick': 'reset',
    'showTips': False,
    'modeBarButtonsToRemove': ['select2d', 'lasso2d'],
}

RANGE_SELECTOR = dict(
    buttons=list([
        dict(count=1, label="1月", step="month", stepmode="backward"),
        dict(count=3, label="3月", step="month", stepmode="backward"),
        dict(count=6, label="6月", step="month", stepmode="backward"),
        dict(count=1, label="1年", step="year", stepmode="backward"),
        dict(step="all", label="全部"),
    ]),
    font=dict(size=11),
    bgcolor="rgba(80,80,80,0.5)",
    activecolor="rgba(120,120,120,0.8)",
)

RANGE_SLIDER = dict(
    visible=True, thickness=0.07,
    bgcolor="rgba(80,80,80,0.4)",
    bordercolor="rgba(150,150,150,0.5)", borderwidth=1,
)

RANGE_BREAKS = [dict(bounds=["sat", "mon"])]

# ========== 初始化数据库 ==========
init_db()

# ========== 认证系统 ==========
with open('.streamlit/config.yaml', encoding='utf-8') as file:
    config = yaml.load(file, Loader=SafeLoader)

authenticator = stauth.Authenticate(
    config['credentials'],
    config['cookie']['name'],
    config['cookie']['key'],
    config['cookie']['expiry_days'],
    auto_hash=False,
)

authenticator.login(
    location='main',
    fields={
        'Form name': '多股对比看板',
        'Username': '用户名',
        'Password': '密码',
        'Login': '登录'
    }
)

if st.session_state.get('authentication_status') is not True:
    if st.session_state.get('authentication_status') is False:
        st.error('用户名或密码错误')
    else:
        st.warning('请输入用户名和密码登录')
    st.caption("本工具仅提供历史数据对比展示，不构成任何投资建议。")
    st.stop()

current_user = st.session_state.get('username', 'unknown')
current_name = st.session_state.get('name', '用户')

with st.sidebar:
    st.markdown(f"**当前用户：{current_name}**")
    authenticator.logout('退出登录', 'sidebar')

# ========== 缓存函数 ==========
@st.cache_data(ttl=86400, show_spinner=False)
def get_stock_list():
    try:
        df = ak.stock_info_a_code_name()
        df = df.iloc[:, :2]
        df.columns = ["代码", "名称"]
        df["代码"] = df["代码"].astype(str).str.zfill(6)
        return df
    except Exception:
        return pd.DataFrame(columns=["代码", "名称"])


@st.cache_data(ttl=60, show_spinner=False)
def get_realtime_data():
    """全A股实时行情快照，使用新浪财经接口"""
    try:
        df = ak.stock_zh_a_spot()
        column_mapping = {
            'code': '代码', 'name': '名称', 'trade': '最新价',
            'pricechange': '涨跌额', 'changepercent': '涨跌幅',
            'buy': '买入', 'sell': '卖出', 'settlement': '昨收',
            'open': '今开', 'high': '最高', 'low': '最低',
            'volume': '成交量', 'amount': '成交额', 'ticktime': '时间',
            'per': '市盈率', 'pb': '市净率',
            'mktcap': '总市值', 'nmc': '流通市值',
            'turnoverratio': '换手率',
        }
        df = df.rename(columns=column_mapping)
        df["代码"] = df["代码"].astype(str).str.zfill(6)
        return df
    except Exception:
        return pd.DataFrame()


@st.cache_data(ttl=86400, show_spinner=False)
def get_industry_boards():
    """行业板块列表（硬编码，避免接口限流）"""
    return [
        "半导体", "白酒", "医药商业", "银行", "证券", "房地产开发",
        "汽车整车", "消费电子", "光伏设备", "航天航空", "农牧饲渔",
        "化学制品", "钢铁行业", "煤炭行业", "有色金属", "电力行业",
        "食品饮料", "家用电器", "通信设备", "计算机设备", "传媒",
        "保险", "石油行业", "环保行业", "旅游酒店"
    ]


@st.cache_data(ttl=3600, show_spinner=False)
def get_board_stocks(board_name):
    """某个行业板块的成分股"""
    try:
        df = ak.stock_board_industry_cons_em(symbol=board_name)
        df = df[["代码", "名称"]].copy()
        df["代码"] = df["代码"].astype(str).str.zfill(6)
        return df
    except Exception:
        return pd.DataFrame(columns=["代码", "名称"])


@st.cache_data(ttl=3600, show_spinner=False)
def fetch_stock_data(symbol, start, end):
    if symbol.startswith('6'):
        full_symbol = f"sh{symbol}"
    else:
        full_symbol = f"sz{symbol}"
    df = ak.stock_zh_a_daily(symbol=full_symbol, start_date=start, end_date=end, adjust="qfq")
    df = df.reset_index()
    column_mapping = {
        'date': '日期', 'open': '开盘', 'close': '收盘',
        'high': '最高', 'low': '最低', 'volume': '成交量',
        'amount': '成交额', 'turnover': '换手率'
    }
    df = df.rename(columns=column_mapping)
    df['日期'] = pd.to_datetime(df['日期'])
    df = df.sort_values('日期').reset_index(drop=True)
    return df


def friendly_error(name, code, err):
    msg = str(err)
    if "RemoteDisconnected" in msg or "Connection aborted" in msg or "ConnectionError" in msg:
        return f"⚠️ {name}（{code}）：数据源暂时繁忙，请稍后重试"
    elif "No data" in msg or "empty" in msg or "NoneType" in msg:
        return f"⚠️ {name}（{code}）：该时间段没有数据，请调整日期范围"
    elif "timeout" in msg.lower() or "timed out" in msg.lower():
        return f"⚠️ {name}（{code}）：网络超时，请检查网络后重试"
    else:
        return f"⚠️ {name}（{code}）：获取失败，请稍后重试"


def apply_chart_layout(fig, x_tick_format, x_nticks, is_candlestick=False):
    fig.update_layout(
        template="plotly_dark", hovermode="x unified", dragmode='pan',
        legend=dict(orientation="h", yanchor="bottom", y=1.05, xanchor="right", x=1),
        margin=dict(l=40, r=20, t=60, b=40),
    )
    if is_candlestick:
        fig.update_layout(xaxis_rangeslider_visible=False)
    fig.update_xaxes(
        tickformat=x_tick_format, nticks=x_nticks,
        rangeselector=RANGE_SELECTOR, rangeslider=RANGE_SLIDER,
        rangebreaks=RANGE_BREAKS,
    )
    fig.update_yaxes(autorange=True)
    return fig


# ========== 初始化 session state ==========
if "selected_stocks" not in st.session_state:
    st.session_state.selected_stocks = [
        ("600519", "贵州茅台"),
        ("000858", "五粮液"),
    ]
if "has_result" not in st.session_state:
    st.session_state.has_result = False
if "start_date" not in st.session_state:
    st.session_state.start_date = datetime.now().date() - timedelta(days=180)
if "end_date" not in st.session_state:
    st.session_state.end_date = datetime.now().date()

stock_list = get_stock_list()

# ========== 页面标题 ==========
st.title("📈 多股对比看板")
st.caption(f"当前用户：{current_name} ｜ 本工具仅提供历史数据对比展示，不构成任何投资建议。")

with st.expander("📖 使用说明（点击展开）", expanded=False):
    st.markdown("""
    **1. 选股**  
    - 搜索框输入代码或名称，点击 ➕ 添加  
    - 在「我的自选」里一键加载已保存的股票  
    - 在「板块选股」里选行业，一键加载板块成分股

    **2. 日期**  
    快捷选择或手动选择起止日期。

    **3. 指标**  
    勾选关心的对比指标。

    **4. 开始分析**  
    点击后等待数据加载，实时行情显示在顶部，对比图表在下方。

    **5. 图表操作**  
    - 顶部：`[1月] [3月] [6月] [1年] [全部]` 快捷按钮  
    - 底部：拖动条，按住左右拖动  
    - 右上角：`＋` `－` `⟲` 缩放按钮
    """)

# ========== 粘性配置栏 ==========
with st.container(key="config_sticky"):
    st.markdown("### ⚙️ 配置")
    tab_stock, tab_date, tab_metrics = st.tabs(["📌 选股", "📅 日期", "📊 指标"])

    # --- 选股 Tab ---
    with tab_stock:
        # 我的自选
        st.markdown("**⭐ 我的自选：**")
        watchlist = get_watchlist(current_user)
        if watchlist:
            for code, name in watchlist:
                c1, c2, c3 = st.columns([6, 1, 1])
                c1.markdown(f"{name}（{code}）")
                if c2.button("加载", key=f"wl_load_{code}"):
                    if (code, name) not in st.session_state.selected_stocks:
                        if len(st.session_state.selected_stocks) < 10:
                            st.session_state.selected_stocks.append((code, name))
                            st.session_state.has_result = False
                            st.rerun()
                if c3.button("✕", key=f"wl_del_{code}"):
                    remove_stock(current_user, code)
                    st.rerun()
        else:
            st.caption("暂无自选，搜索股票后点⭐添加")

        st.markdown("---")

        # 已选列表
        st.markdown("**已选股票（最多10只）：**")
        if st.session_state.selected_stocks:
            for i, (code, name) in enumerate(st.session_state.selected_stocks, 1):
                c1, c2 = st.columns([10, 1])
                c1.markdown(f"**{i}.** {name}（{code}）")
                if c2.button("✕", key=f"del_{code}_{i}"):
                    st.session_state.selected_stocks.pop(i - 1)
                    st.session_state.has_result = False
                    st.rerun()
        else:
            st.caption("尚未选择股票")

        st.markdown("---")

        # 搜索添加
        st.markdown("**🔍 搜索添加：**")
        search = st.text_input(
            "搜索股票", key="search_input",
            placeholder="输入代码或名称，如 600519 或 茅台",
            label_visibility="collapsed"
        )
        if search:
            matches = stock_list[
                stock_list["代码"].str.contains(search, na=False) |
                stock_list["名称"].str.contains(search, na=False)
            ].head(6)
            if matches.empty:
                st.caption("未找到匹配股票")
            else:
                if len(st.session_state.selected_stocks) >= 10:
                    st.caption("⚠️ 已达上限（10 只）")
                else:
                    for _, row in matches.iterrows():
                        code = row["代码"]
                        name = row["名称"]
                        already_selected = (code, name) in st.session_state.selected_stocks
                        already_wl = (code, name) in watchlist
                        c1, c2, c3 = st.columns([6, 1, 1])
                        c1.markdown(f"{code} {name}")
                        if c2.button("➕", key=f"add_{code}", help="加入对比"):
                            if not already_selected and len(st.session_state.selected_stocks) < 10:
                                st.session_state.selected_stocks.append((code, name))
                                st.session_state.has_result = False
                                st.rerun()
                        if not already_wl:
                            if c3.button("⭐", key=f"star_{code}", help="加入自选"):
                                add_stock(current_user, code, name)
                                st.rerun()

        st.markdown("---")

        # 板块选股
        st.markdown("**🏭 板块选股：**")
        boards = get_industry_boards()
        selected_board = st.selectbox(
            "选择行业板块", ["请选择..."] + boards, key="board_select",
            label_visibility="collapsed"
        )
        if selected_board and selected_board != "请选择...":
            board_stocks = get_board_stocks(selected_board)
            if board_stocks.empty:
                st.caption("该板块暂无数据，请换一个板块")
            else:
                st.caption(f"共 {len(board_stocks)} 只成分股，显示前 20 只：")
                for _, row in board_stocks.head(20).iterrows():
                    code = row["代码"]
                    name = row["名称"]
                    already_selected = (code, name) in st.session_state.selected_stocks
                    c1, c2, c3 = st.columns([6, 1, 1])
                    c1.markdown(f"{code} {name}")
                    if c2.button("➕", key=f"badd_{code}"):
                        if not already_selected and len(st.session_state.selected_stocks) < 10:
                            st.session_state.selected_stocks.append((code, name))
                            st.session_state.has_result = False
                            st.rerun()
                    if (code, name) not in watchlist:
                        if c3.button("⭐", key=f"bstar_{code}"):
                            add_stock(current_user, code, name)
                            st.rerun()

    # --- 日期 Tab ---
    with tab_date:
        today = datetime.now().date()
        qc1, qc2, qc3, qc4, qc5 = st.columns(5)
        if qc1.button("近1月", width='stretch'):
            st.session_state.start_date = today - timedelta(days=30)
            st.session_state.end_date = today
            st.rerun()
        if qc2.button("近3月", width='stretch'):
            st.session_state.start_date = today - timedelta(days=90)
            st.session_state.end_date = today
            st.rerun()
        if qc3.button("近6月", width='stretch'):
            st.session_state.start_date = today - timedelta(days=180)
            st.session_state.end_date = today
            st.rerun()
        if qc4.button("近1年", width='stretch'):
            st.session_state.start_date = today - timedelta(days=365)
            st.session_state.end_date = today
            st.rerun()
        if qc5.button("近3年", width='stretch'):
            st.session_state.start_date = today - timedelta(days=1095)
            st.session_state.end_date = today
            st.rerun()
        dc1, dc2 = st.columns(2)
        with dc1:
            start_date = st.date_input("开始日期", key="start_date", format="YYYY/MM/DD")
        with dc2:
            end_date = st.date_input("结束日期", key="end_date", format="YYYY/MM/DD")

    # --- 指标 Tab ---
    with tab_metrics:
        mc1, mc2, mc3 = st.columns(3)
        with mc1:
            st.markdown("**价格类**")
            price_options = [
                "累计收益率", "归一化价格", "日涨跌幅",
                "收盘价对比", "K线图", "均线对比（MA5/MA10/MA20）", "振幅"
            ]
            price_metrics = []
            for m in price_options:
                default_on = (m == "累计收益率")
                if st.checkbox(m, value=default_on, key=f"pm_{m}"):
                    price_metrics.append(m)
        with mc2:
            st.markdown("**成交类**")
            volume_options = ["成交量", "换手率", "成交额"]
            volume_metrics = []
            for m in volume_options:
                if st.checkbox(m, value=False, key=f"vm_{m}"):
                    volume_metrics.append(m)
        with mc3:
            st.markdown("**统计类**")
            show_summary = st.checkbox("指标汇总表", value=True, key="show_summary")
            show_correlation = st.checkbox("相关性矩阵", value=False, key="show_correlation")

    if st.button("🚀 开始分析", type="primary", width='stretch'):
        st.session_state.has_result = True


# ========== 结果区 ==========
if not st.session_state.has_result:
    st.info("👉 请在上方「配置」区域选择股票、日期和指标，然后点击「开始分析」")
else:
    if not st.session_state.selected_stocks:
        st.error("请先选择至少一只股票。")
        st.stop()

    resolved = st.session_state.selected_stocks
    total = len(resolved)

    # ========== 实时行情卡片 ==========
    st.markdown("### ⚡ 实时行情")
    realtime_df = get_realtime_data()
    if not realtime_df.empty:
        selected_codes = [code for code, _ in resolved]
        rt = realtime_df[realtime_df["代码"].isin(selected_codes)]

        if not rt.empty:
            rt_records = rt.to_dict("records")
            rows = (len(rt_records) + 4) // 5
            for r in range(rows):
                cols = st.columns(min(5, len(rt_records) - r * 5))
                for i, rec in enumerate(rt_records[r * 5: r * 5 + 5]):
                    with cols[i]:
                        latest = rec.get("最新价", "-")
                        change_pct = rec.get("涨跌幅", 0)
                        change_amt = rec.get("涨跌额", 0)
                        try:
                            delta_str = f"{float(change_amt):+.2f} ({float(change_pct):+.2f}%)"
                        except Exception:
                            delta_str = "-"
                        st.metric(
                            label=f"{rec.get('名称', '')}（{rec.get('代码', '')}）",
                            value=f"{latest}",
                            delta=delta_str
                        )
            with st.expander("📋 查看详细数据", expanded=False):
                show_cols = ["代码", "名称", "最新价", "涨跌幅", "涨跌额",
                             "成交量", "成交额", "换手率", "市盈率", "市净率"]
                show_cols = [c for c in show_cols if c in rt.columns]
                st.dataframe(rt[show_cols], width='stretch', hide_index=True)
        else:
            st.caption("无实时数据")
    else:
        st.caption("实时行情获取失败，不影响历史数据对比。")

    st.markdown("---")

    # ========== 历史数据获取 ==========
    progress_bar = st.progress(0, text="正在准备...")
    status_text = st.empty()
    data_dict = {}
    error_list = []

    for idx, (code, name) in enumerate(resolved, 1):
        status_text.info(f"正在获取第 {idx}/{total} 只：{name}（{code}）")
        progress_bar.progress(idx / total, text=f"进度：{idx}/{total}")
        try:
            df = fetch_stock_data(
                code,
                str(start_date).replace("-", ""),
                str(end_date).replace("-", "")
            )
            if df is not None and not df.empty:
                data_dict[name] = df
            else:
                error_list.append(f"⚠️ {name}（{code}）：该时间段没有数据")
        except Exception as e:
            error_list.append(friendly_error(name, code, e))

    progress_bar.empty()
    status_text.empty()

    for err in error_list:
        st.warning(err)

    if not data_dict:
        st.error("所有股票都没有获取到数据。请检查网络，或稍后重试。")
        st.stop()

    result = {}
    for name, df in data_dict.items():
        d = df.copy()
        d["日收益率"] = d["收盘"].pct_change()
        result[name] = d.set_index("日期")

    all_dates = pd.concat([df.index.to_series() for df in result.values()])
    date_span_days = (all_dates.max() - all_dates.min()).days

    if date_span_days <= 60:
        x_tick_format = "%m.%d"; x_nticks = 10
    elif date_span_days <= 180:
        x_tick_format = "%m.%d"; x_nticks = 8
    elif date_span_days <= 365:
        x_tick_format = "%Y.%m"; x_nticks = 10
    else:
        x_tick_format = "%Y.%m"; x_nticks = 12

    # ========== 图表渲染 ==========
    for metric in price_metrics:
        st.subheader(f"📈 {metric}")

        if metric == "累计收益率":
            fig = go.Figure()
            for name, df in result.items():
                cum = (1 + df["日收益率"].fillna(0)).cumprod() - 1
                fig.add_trace(go.Scatter(x=cum.index, y=cum * 100, mode="lines", name=name))
            fig.update_layout(height=420, yaxis_title="累计收益率（%）")
            apply_chart_layout(fig, x_tick_format, x_nticks)
            st.plotly_chart(fig, width='stretch', config=PLOTLY_CONFIG)

        elif metric == "归一化价格":
            fig = go.Figure()
            for name, df in result.items():
                norm = df["收盘"] / df["收盘"].iloc[0] * 100
                fig.add_trace(go.Scatter(x=norm.index, y=norm, mode="lines", name=name))
            fig.update_layout(height=420, yaxis_title="归一化价格（起点=100）")
            apply_chart_layout(fig, x_tick_format, x_nticks)
            st.plotly_chart(fig, width='stretch', config=PLOTLY_CONFIG)

        elif metric == "日涨跌幅":
            fig = go.Figure()
            for name, df in result.items():
                fig.add_trace(go.Scatter(x=df.index, y=df["日收益率"] * 100, mode="lines", name=name))
            fig.update_layout(height=420, yaxis_title="日涨跌幅（%）")
            apply_chart_layout(fig, x_tick_format, x_nticks)
            st.plotly_chart(fig, width='stretch', config=PLOTLY_CONFIG)

        elif metric == "收盘价对比":
            fig = go.Figure()
            for name, df in result.items():
                fig.add_trace(go.Scatter(x=df.index, y=df["收盘"], mode="lines", name=name))
            fig.update_layout(height=420, yaxis_title="收盘价（元）")
            apply_chart_layout(fig, x_tick_format, x_nticks)
            st.plotly_chart(fig, width='stretch', config=PLOTLY_CONFIG)

        elif metric == "K线图":
            kline_stock = st.selectbox("选择要查看的股票", list(result.keys()), key="kline_select")
            df = result[kline_stock]
            fig = go.Figure()
            fig.add_trace(go.Candlestick(
                x=df.index, open=df['开盘'], high=df['最高'], low=df['最低'], close=df['收盘'],
                name=kline_stock,
                increasing_line_color='#ff4b4b', decreasing_line_color='#00c853',
                increasing_fillcolor='#ff4b4b', decreasing_fillcolor='#00c853'
            ))
            fig.update_layout(title=f"{kline_stock} K线图", height=480, yaxis_title="价格（元）")
            apply_chart_layout(fig, x_tick_format, x_nticks, is_candlestick=True)
            st.plotly_chart(fig, width='stretch', config=PLOTLY_CONFIG)
            st.caption("红色代表上涨，绿色代表下跌。")

        elif metric == "均线对比（MA5/MA10/MA20）":
            ma_stock = st.selectbox("选择要查看的股票", list(result.keys()), key="ma_select")
            df = result[ma_stock]
            fig = go.Figure()
            fig.add_trace(go.Scatter(
                x=df.index, y=df['收盘'], mode="lines", name="收盘价",
                line=dict(color='white', width=1, dash='dot')
            ))
            for period in [5, 10, 20]:
                ma = df['收盘'].rolling(period).mean()
                fig.add_trace(go.Scatter(x=df.index, y=ma, mode="lines", name=f"MA{period}"))
            fig.update_layout(title=f"{ma_stock} 均线图", height=450, yaxis_title="价格（元）")
            apply_chart_layout(fig, x_tick_format, x_nticks)
            st.plotly_chart(fig, width='stretch', config=PLOTLY_CONFIG)

        elif metric == "振幅":
            fig = go.Figure()
            for name, df in result.items():
                if '最高' in df.columns and '最低' in df.columns:
                    amplitude = (df['最高'] - df['最低']) / df['收盘'].shift(1) * 100
                    fig.add_trace(go.Scatter(x=df.index, y=amplitude, mode="lines", name=name))
            fig.update_layout(height=420, yaxis_title="振幅（%）")
            apply_chart_layout(fig, x_tick_format, x_nticks)
            st.plotly_chart(fig, width='stretch', config=PLOTLY_CONFIG)

    if "成交量" in volume_metrics:
        st.subheader("📊 成交量对比")
        fig = go.Figure()
        for name, df in result.items():
            fig.add_trace(go.Bar(x=df.index, y=df["成交量"], name=name, opacity=0.7))
        fig.update_layout(height=380, yaxis_title="成交量", barmode="group")
        apply_chart_layout(fig, x_tick_format, x_nticks)
        st.plotly_chart(fig, width='stretch', config=PLOTLY_CONFIG)

    if "换手率" in volume_metrics:
        st.subheader("📊 换手率对比")
        fig = go.Figure()
        has_data = False
        for name, df in result.items():
            if "换手率" in df.columns:
                fig.add_trace(go.Scatter(x=df.index, y=df["换手率"], mode="lines", name=name))
                has_data = True
        if has_data:
            fig.update_layout(height=380, yaxis_title="换手率（%）")
            apply_chart_layout(fig, x_tick_format, x_nticks)
            st.plotly_chart(fig, width='stretch', config=PLOTLY_CONFIG)
        else:
            st.info("所选股票没有换手率数据。")

    if "成交额" in volume_metrics:
        st.subheader("📊 成交额对比")
        fig = go.Figure()
        has_data = False
        for name, df in result.items():
            if "成交额" in df.columns:
                fig.add_trace(go.Bar(x=df.index, y=df["成交额"], name=name, opacity=0.7))
                has_data = True
        if has_data:
            fig.update_layout(height=380, yaxis_title="成交额（元）", barmode="group")
            apply_chart_layout(fig, x_tick_format, x_nticks)
            st.plotly_chart(fig, width='stretch', config=PLOTLY_CONFIG)
        else:
            st.info("所选股票没有成交额数据。")

    if show_summary:
        st.markdown("---")
        st.subheader("📋 指标汇总表")
        summary_data = {}
        for name, df in result.items():
            returns = df["日收益率"].dropna()
            if len(returns) == 0:
                continue
            cum_ret = (1 + returns).prod() - 1
            vol = returns.std() * np.sqrt(252)
            cum_series = (1 + returns).cumprod()
            max_dd = (cum_series / cum_series.cummax() - 1).min()
            sharpe = (returns.mean() * 252) / vol if vol > 0 else 0
            summary_data[name] = {
                "累计收益率": f"{cum_ret*100:.2f}%",
                "年化波动率": f"{vol*100:.2f}%",
                "最大回撤": f"{max_dd*100:.2f}%",
                "夏普比率": f"{sharpe:.2f}",
                "日均涨跌幅": f"{returns.mean()*100:.3f}%",
                "最大单日涨幅": f"{returns.max()*100:.2f}%",
                "最大单日跌幅": f"{returns.min()*100:.2f}%"
            }
        if summary_data:
            st.dataframe(pd.DataFrame(summary_data), width='stretch')

    if show_correlation and len(result) >= 2:
        st.markdown("---")
        st.subheader("🔗 日收益率相关性矩阵")
        returns_df = pd.DataFrame({
            name: df["日收益率"] for name, df in result.items()
        }).dropna()
        if len(returns_df) >= 2:
            corr = returns_df.corr()
            fig = px.imshow(
                corr, text_auto=".2f", color_continuous_scale="RdBu_r",
                zmin=-1, zmax=1, aspect="auto"
            )
            fig.update_layout(template="plotly_dark", height=380)
            st.plotly_chart(fig, width='stretch', config=PLOTLY_CONFIG)
            st.caption("数值越接近 1，走势越同步；越接近 -1，走势越相反。")

    st.markdown("---")
    st.caption("⚠️ 本工具仅提供历史数据对比展示，所有数据来源于公开接口，不构成任何投资建议。据此操作，风险自负。")