import streamlit as st
import pandas as pd
import io
import plotly.graph_objects as go

st.set_page_config(page_title="Rotina 8020", layout="wide")
st.markdown("""<style>
[data-testid="stMetricValue"] { font-size: 2rem !important; font-weight: 700; }
[data-testid="stMetricDelta"] { font-size: 1rem !important; }
.dataframe tbody tr:nth-child(even) { background-color: #1a202c !important; }
.dataframe tbody tr:hover { background-color: #2d3748 !important; }
.dataframe th { background-color: #0d1117 !important; color: #ffffff !important; font-weight: bold !important; }
</style>""", unsafe_allow_html=True)

st.title("Rotina 8020 - Vendas Por Cliente e Rede")

ORDER_MESES = {'jan':1,'fev':2,'mar':3,'abr':4,'mai':5,'jun':6,'jul':7,'ago':8,'set':9,'out':10,'nov':11,'dez':12}

def chave_cronologica(texto):
    try:
        m, a = str(texto).split('/')
        return (int(a), ORDER_MESES.get(m.lower(), 0))
    except Exception:
        return (99, 99)

def fmt_brl(valor):
    try:
        return "R$ " + f"{int(valor):,}".replace(',', '.')
    except Exception:
        return "R$ 0"

def fmt_pct(valor):
    try:
        return f"{valor:.2f}%"
    except Exception:
        return "0.00%"

PLOT_BG = "#0d1117"
PLOT_GRID = "#1a202c"
PLOT_FONT = "#e2e8f0"

def base_layout(height=360):
    return dict(
        paper_bgcolor=PLOT_BG,
        plot_bgcolor=PLOT_BG,
        font=dict(color=PLOT_FONT, family="sans-serif"),
        margin=dict(l=10, r=120, t=40, b=10),
        height=height,
        xaxis=dict(gridcolor=PLOT_GRID, zerolinecolor=PLOT_GRID),
        yaxis=dict(gridcolor=PLOT_GRID, zerolinecolor=PLOT_GRID),
    )

@st.cache_data(show_spinner="Carregando base de dados...")
def carregar_base():
    df = pd.read_parquet("vendas_8020.parquet")
    if 'PERIODO_LIMPO' not in df.columns and 'PERIODO' in df.columns:
        df['PERIODO_LIMPO'] = df['PERIODO'].astype(str).str.strip()
    else:
        df['PERIODO_LIMPO'] = df['PERIODO_LIMPO'].astype(str).str.strip()
    df['ANO_EIXO'] = df['PERIODO_LIMPO'].apply(
        lambda x: "20" + x.split('/')[1] if '/' in str(x) else 'Desconhecido'
    )
    df['CODFILIAL'] = df['CODFILIAL'].map(
        {'1': 'Matriz - 1', '2': 'Loja - 2', 1: 'Matriz - 1', 2: 'Loja - 2'}
    ).fillna(df['CODFILIAL'].astype(str))
    for col in ['QT', 'TVENDA', 'TLUCRO']:
        if col in df.columns:
            df[col] = pd.to_numeric(df[col], errors='coerce').fillna(0)
    return df

dados_originais = carregar_base()

st.sidebar.header("Filtros de Selecao")
anos_disponiveis = sorted(dados_originais['ANO_EIXO'].unique(), reverse=True)
anos_selecionados = st.sidebar.multiselect("Ano", anos_disponiveis, default=anos_disponiveis)
df_temp = dados_originais[dados_originais['ANO_EIXO'].isin(anos_selecionados)] if anos_selecionados else dados_originais
todos_meses = sorted(df_temp['PERIODO_LIMPO'].unique(), key=chave_cronologica)
meses_selecionados = st.sidebar.multiselect("Meses Disponiveis", todos_meses, default=todos_meses)
filiais_disponiveis = sorted(df_temp['CODFILIAL'].unique())
filial_sel = st.sidebar.multiselect("Unidade / Filial", filiais_disponiveis, default=filiais_disponiveis)
redes_disponiveis = sorted(df_temp['REDE'].dropna().unique())
rede_sel = st.sidebar.multiselect("Rede de Clientes", redes_disponiveis, default=[])
marcas_disponiveis = sorted(df_temp['MARCA'].dropna().unique()) if 'MARCA' in df_temp.columns else []
marca_sel = st.sidebar.multiselect("Marca do Produto", marcas_disponiveis, default=[])
busca_produto = st.sidebar.text_input("Buscar por Nome do Produto")
st.sidebar.markdown("---")
st.sidebar.header("Entrada de Listas (Excel)")

def processar_lista_input(texto):
    if not texto:
        return []
    return [l.strip() for l in texto.replace('\t', ' ').replace(',', ' ').split('\n') if l.strip()]

with st.sidebar.expander("Filtragem Avancada por Lotes"):
    input_codrede = st.text_area("Lista de Codigos de Rede")
    input_codcli  = st.text_area("Lista de Codigos de Cliente")
    input_codprod = st.text_area("Lista de Codigos de Produto")
    input_ean     = st.text_area("Lista de Codigos EAN")
    input_ncm     = st.text_area("Lista de Codigos NCM")

df_filtrado = dados_originais.copy()
if anos_selecionados:
    df_filtrado = df_filtrado[df_filtrado['ANO_EIXO'].isin(anos_selecionados)]
if meses_selecionados:
    df_filtrado = df_filtrado[df_filtrado['PERIODO_LIMPO'].isin(meses_selecionados)]
if filial_sel:
    df_filtrado = df_filtrado[df_filtrado['CODFILIAL'].isin(filial_sel)]
if rede_sel:
    df_filtrado = df_filtrado[df_filtrado['REDE'].isin(rede_sel)]
if marca_sel:
    df_filtrado = df_filtrado[df_filtrado['MARCA'].isin(marca_sel)]
if busca_produto:
    df_filtrado = df_filtrado[df_filtrado['DESCRICAO'].str.contains(busca_produto, case=False, na=False)]
for campo, lista in [
    ('CODREDE', processar_lista_input(input_codrede)),
    ('CODCLI',  processar_lista_input(input_codcli)),
    ('CODPROD', processar_lista_input(input_codprod)),
    ('EAN',     processar_lista_input(input_ean)),
    ('NCM',     processar_lista_input(input_ncm)),
]:
    if lista and campo in df_filtrado.columns:
        df_filtrado = df_filtrado[df_filtrado[campo].isin(lista)]

tab_clientes, tab_produtos, tab_inteligencia = st.tabs([
    "Clientes / Rede",
    "Produtos / Marca",
    "Inteligencia de Negocio"
])

# ---------------------------------------------------------------
# ABA 1 - CLIENTES
# ---------------------------------------------------------------
with tab_clientes:
    if df_filtrado.empty:
        st.warning("Sem dados para os filtros aplicados.")
    else:
        colunas_meses = sorted(df_filtrado['PERIODO_LIMPO'].unique(), key=chave_cronologica)
        tot_fat  = df_filtrado['TVENDA'].sum()
        tot_luc  = df_filtrado['TLUCRO'].sum() if 'TLUCRO' in df_filtrado.columns else 0
        tot_pos  = df_filtrado['CODCLI'].nunique()
        margem_g = (tot_luc / tot_fat * 100) if tot_fat > 0 else 0
        delta_str = None
        if len(colunas_meses) >= 2:
            mes_atual = colunas_meses[-1]
            mes_ant   = colunas_meses[-2]
            fat_atual = df_filtrado[df_filtrado['PERIODO_LIMPO'] == mes_atual]['TVENDA'].sum()
            fat_ant   = df_filtrado[df_filtrado['PERIODO_LIMPO'] == mes_ant]['TVENDA'].sum()
            if fat_ant > 0:
                delta_val = (fat_atual - fat_ant) / fat_ant * 100
                delta_str = f"{delta_val:+.1f}% vs {mes_ant}"
        st.write("### Indicadores Consolidados do Periodo")
        m1, m2, m3, m4 = st.columns(4)
        m1.metric("Faturamento Bruto",      fmt_brl(tot_fat), delta=delta_str)
        m2.metric("Lucro Bruto",            fmt_brl(tot_luc))
        m3.metric("Clientes Positivados",   f"{tot_pos:,}".replace(',', '.'))
        m4.metric("Margem de Contribuicao", fmt_pct(margem_g))
        st.markdown("---")
        resumo_temp = (
            df_filtrado.groupby('PERIODO_LIMPO')
            .agg(Faturamento=('TVENDA', 'sum'), Positivacoes=('CODCLI', 'nunique'))
            .reindex(colunas_meses)
            .fillna(0)
        )
        st.write("### Resumo de Desempenho Mensal")
        tabela_topo = {"Metrica": ["Total Venda", "Total Positivacoes"]}
        for m in colunas_meses:
            tabela_topo[m] = [
                fmt_brl(resumo_temp.loc[m, 'Faturamento']),
                f"{int(resumo_temp.loc[m, 'Positivacoes']):,}".replace(',', '.'),
            ]
        st.table(pd.DataFrame(tabela_topo))
        matrix_cli = (
            df_filtrado.pivot_table(
                index=['CODCLI', 'CLIENTE'],
                columns='PERIODO_LIMPO',
                values='TVENDA',
                aggfunc='sum'
            )
            .fillna(0)
        )
        matrix_cli = matrix_cli.reindex(columns=colunas_meses, fill_value=0)
        matrix_cli['Total'] = matrix_cli[colunas_meses].sum(axis=1)
        ult_3 = colunas_meses[-3:] if len(colunas_meses) >= 3 else colunas_meses
        matrix_cli['Media Ult. 3 Meses'] = matrix_cli[ult_3].mean(axis=1)
        matrix_cli = matrix_cli.sort_values('Total', ascending=False).reset_index()
        matrix_cli = matrix_cli.rename(columns={'CODCLI': 'Codigo', 'CLIENTE': 'Cliente'})
        matrix_cli['Acumulado'] = matrix_cli['Total'].cumsum()
        soma_v = matrix_cli['Total'].sum()
        matrix_cli['Pct Acumulado'] = (matrix_cli['Acumulado'] / soma_v * 100) if soma_v > 0 else 0
        matrix_cli['Curva ABC'] = matrix_cli['Pct Acumulado'].apply(
            lambda x: 'A' if x <= 80 else ('B' if x <= 95 else 'C')
        )
        colunas_exib = ['Curva ABC', 'Codigo', 'Cliente'] + colunas_meses + ['Media Ult. 3 Meses', 'Total']
        cols_num = colunas_meses + ['Media Ult. 3 Meses', 'Total']
        st.write("### Grade de Faturamento por Cliente e Rede")
        st.dataframe(
            matrix_cli[colunas_exib].style.format({c: fmt_brl for c in cols_num}),
            use_container_width=True,
            height=450
        )
        buf = io.BytesIO()
        with pd.ExcelWriter(buf, engine='xlsxwriter') as w:
            matrix_cli[colunas_exib].to_excel(w, index=False, sheet_name='Clientes 8020')
        st.download_button(
            "Exportar Clientes para Excel",
            data=buf.getvalue(),
            file_name="rotina_8020_clientes.xlsx",
            mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
        )

# ---------------------------------------------------------------
# ABA 2 - PRODUTOS
# ---------------------------------------------------------------
with tab_produtos:
    if df_filtrado.empty:
        st.warning("Sem dados para os filtros aplicados.")
    else:
        st.write("### Performance de Linhas de Produtos e Marcas")
        agg_cols = {'QT': 'sum', 'TVENDA': 'sum'}
        grp_cols = ['CODPROD', 'DESCRICAO']
        if 'MARCA' in df_filtrado.columns:
            grp_cols.append('MARCA')
        if 'NCM' in df_filtrado.columns:
            grp_cols.append('NCM')
        if 'TLUCRO' in df_filtrado.columns:
            agg_cols['TLUCRO'] = 'sum'
        df_prod = (
            df_filtrado.groupby(grp_cols)
            .agg(agg_cols)
            .sort_values('TVENDA', ascending=False)
            .reset_index()
        )
        df_prod['Acumulado'] = df_prod['TVENDA'].cumsum()
        soma_p = df_prod['TVENDA'].sum()
        df_prod['Pct Acumulado'] = (df_prod['Acumulado'] / soma_p * 100) if soma_p > 0 else 0
        df_prod['Curva ABC'] = df_prod['Pct Acumulado'].apply(
            lambda x: 'A' if x <= 80 else ('B' if x <= 95 else 'C')
        )
        if 'TLUCRO' in df_prod.columns:
            df_prod['Margem %'] = (df_prod['TLUCRO'] / df_prod['TVENDA'] * 100).where(df_prod['TVENDA'] > 0, 0)
        rename_map = {
            'CODPROD': 'Codigo', 'DESCRICAO': 'Produto',
            'MARCA': 'Marca', 'QT': 'Vol. Caixas',
            'TVENDA': 'Faturamento', 'TLUCRO': 'Lucro Bruto'
        }
        df_prod = df_prod.rename(columns={k: v for k, v in rename_map.items() if k in df_prod.columns})
        base_cols = ['Curva ABC', 'Codigo', 'Produto']
        if 'Marca' in df_prod.columns:
            base_cols.append('Marca')
        if 'NCM' in df_prod.columns:
            base_cols.append('NCM')
        base_cols += ['Vol. Caixas', 'Faturamento']
        if 'Lucro Bruto' in df_prod.columns:
            base_cols.append('Lucro Bruto')
        if 'Margem %' in df_prod.columns:
            base_cols.append('Margem %')
        fmt_prod = {'Vol. Caixas': lambda x: f"{int(x):,}".replace(',', '.'), 'Faturamento': fmt_brl}
        if 'Lucro Bruto' in df_prod.columns:
            fmt_prod['Lucro Bruto'] = fmt_brl
        if 'Margem %' in df_prod.columns:
            fmt_prod['Margem %'] = fmt_pct
        st.dataframe(
            df_prod[base_cols].style.format(fmt_prod),
            use_container_width=True,
            height=400
        )

        if 'MARCA' in df_filtrado.columns:
            st.write("### Participacao de Faturamento por Marca (Top 15)")
            df_marca_g = (
                df_filtrado.groupby('MARCA')['TVENDA']
                .sum()
                .sort_values(ascending=True)
                .tail(15)
                .reset_index()
            )
            df_marca_g['fat_fmt'] = df_marca_g['TVENDA'].apply(fmt_brl)
            fig_marca = go.Figure(go.Bar(
                x=df_marca_g['TVENDA'],
                y=df_marca_g['MARCA'],
                orientation='h',
                marker_color='#3b82f6',
                text=df_marca_g['fat_fmt'],
                textposition='outside',
                hovertemplate='<b>%{y}</b><br>%{customdata}<extra></extra>',
                customdata=df_marca_g['fat_fmt'],
            ))
            layout_marca = base_layout(480)
            layout_marca['xaxis'] = dict(gridcolor=PLOT_GRID, showticklabels=False, tickvals=[])
            layout_marca['yaxis'] = dict(gridcolor=PLOT_GRID)
            layout_marca['margin'] = dict(l=10, r=150, t=40, b=10)
            fig_marca.update_layout(**layout_marca)
            st.plotly_chart(fig_marca, use_container_width=True)

        buf_p = io.BytesIO()
        with pd.ExcelWriter(buf_p, engine='xlsxwriter') as w:
            df_prod[base_cols].to_excel(w, index=False, sheet_name='Produtos 8020')
        st.download_button(
            "Exportar Produtos para Excel",
            data=buf_p.getvalue(),
            file_name="rotina_8020_produtos.xlsx",
            mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
        )

# ---------------------------------------------------------------
# ABA 3 - INTELIGENCIA DE NEGOCIO
# ---------------------------------------------------------------
with tab_inteligencia:
    if df_filtrado.empty:
        st.warning("Sem dados para os filtros aplicados.")
    else:
        colunas_meses_ib = sorted(df_filtrado['PERIODO_LIMPO'].unique(), key=chave_cronologica)

        st.write("### Evolucao de Faturamento Mensal")
        serie_fat = (
            df_filtrado.groupby('PERIODO_LIMPO')['TVENDA']
            .sum()
            .reindex(colunas_meses_ib)
            .fillna(0)
        )
        fat_fmt_list = [fmt_brl(v) for v in serie_fat.values]
        fig_fat = go.Figure(go.Scatter(
            x=serie_fat.index.tolist(),
            y=serie_fat.values,
            mode='lines+markers',
            line=dict(color='#3b82f6', width=2),
            marker=dict(size=7, color='#60a5fa'),
            fill='tozeroy',
            fillcolor='rgba(59,130,246,0.10)',
            hovertemplate='<b>%{x}</b><br>Faturamento: %{customdata}<extra></extra>',
            customdata=fat_fmt_list,
        ))
        layout_fat = base_layout(360)
        layout_fat['yaxis'] = dict(gridcolor=PLOT_GRID, tickformat=',', tickprefix='R$ ')
        fig_fat.update_layout(**layout_fat)
        st.plotly_chart(fig_fat, use_container_width=True)

        if 'TLUCRO' in df_filtrado.columns:
            st.write("### Margem de Contribuicao por Mes (%)")
            serie_luc_m = (
                df_filtrado.groupby('PERIODO_LIMPO')['TLUCRO']
                .sum()
                .reindex(colunas_meses_ib)
                .fillna(0)
            )
            serie_margem = (serie_luc_m / serie_fat * 100).fillna(0)
            marg_fmt_list = [fmt_pct(v) for v in serie_margem.values]
            fig_marg = go.Figure(go.Scatter(
                x=serie_margem.index.tolist(),
                y=serie_margem.values,
                mode='lines+markers',
                line=dict(color='#10b981', width=2),
                marker=dict(size=7, color='#34d399'),
                fill='tozeroy',
                fillcolor='rgba(16,185,129,0.10)',
                hovertemplate='<b>%{x}</b><br>Margem: %{customdata}<extra></extra>',
                customdata=marg_fmt_list,
            ))
            layout_marg = base_layout(300)
            layout_marg['yaxis'] = dict(gridcolor=PLOT_GRID, ticksuffix='%')
            fig_marg.update_layout(**layout_marg)
            st.plotly_chart(fig_marg, use_container_width=True)

        st.markdown("---")

        st.write("### Clientes Novos vs Recorrentes por Mes")
        clientes_por_mes = (
            df_filtrado.groupby(['PERIODO_LIMPO', 'CODCLI'])
            .size()
            .reset_index(name='pedidos')
        )
        seen = set()
        novos_list       = []
        recorrentes_list = []
        for mes in colunas_meses_ib:
            clis_mes = set(clientes_por_mes[clientes_por_mes['PERIODO_LIMPO'] == mes]['CODCLI'])
            novos_list.append(len(clis_mes - seen))
            recorrentes_list.append(len(clis_mes & seen))
            seen |= clis_mes
        fig_nr = go.Figure()
        fig_nr.add_trace(go.Bar(
            name='Novos',
            x=colunas_meses_ib,
            y=novos_list,
            marker_color='#f59e0b',
            hovertemplate='<b>%{x}</b><br>Novos: %{y}<extra></extra>',
        ))
        fig_nr.add_trace(go.Bar(
            name='Recorrentes',
            x=colunas_meses_ib,
            y=recorrentes_list,
            marker_color='#3b82f6',
            hovertemplate='<b>%{x}</b><br>Recorrentes: %{y}<extra></extra>',
        ))
        layout_nr = base_layout(320)
        layout_nr['barmode'] = 'group'
        layout_nr['legend'] = dict(orientation='h', yanchor='bottom', y=1.02, xanchor='right', x=1)
        fig_nr.update_layout(**layout_nr)
        st.plotly_chart(fig_nr, use_container_width=True)

        st.markdown("---")

        st.write("### Top 10 Clientes por Faturamento")
        top10_cli = (
            df_filtrado.groupby(['CODCLI', 'CLIENTE'])['TVENDA']
            .sum()
            .sort_values(ascending=False)
            .head(10)
            .reset_index()
        )
        top10_cli.columns = ['Codigo', 'Cliente', 'Faturamento']
        top10_cli['Faturamento R$'] = top10_cli['Faturamento'].apply(fmt_brl)
        soma_top = top10_cli['Faturamento'].sum()
        top10_cli['% do Total'] = top10_cli['Faturamento'].apply(
            lambda x: fmt_pct(x / soma_top * 100) if soma_top > 0 else '0.00%'
        )
        st.dataframe(
            top10_cli[['Codigo', 'Cliente', 'Faturamento R$', '% do Total']],
            use_container_width=True,
            hide_index=True
        )
        top10_plot = top10_cli.sort_values('Faturamento', ascending=True)
        fig_top10 = go.Figure(go.Bar(
            x=top10_plot['Faturamento'],
            y=top10_plot['Cliente'],
            orientation='h',
            marker_color='#6366f1',
            text=top10_plot['Faturamento R$'],
            textposition='outside',
            hovertemplate='<b>%{y}</b><br>%{customdata}<extra></extra>',
            customdata=top10_plot['Faturamento R$'],
        ))
        layout_top10 = base_layout(400)
        layout_top10['xaxis'] = dict(gridcolor=PLOT_GRID, showticklabels=False, tickvals=[])
        layout_top10['yaxis'] = dict(gridcolor=PLOT_GRID)
        layout_top10['margin'] = dict(l=10, r=150, t=40, b=10)
        fig_top10.update_layout(**layout_top10)
        st.plotly_chart(fig_top10, use_container_width=True)

        st.markdown("---")

        st.write("### Risco de Churn - Clientes que nao compraram no ultimo mes")
        df_churn  = pd.DataFrame()
        ausentes  = set()
        penultimo = None
        if len(colunas_meses_ib) >= 2:
            ultimo_mes  = colunas_meses_ib[-1]
            penultimo   = colunas_meses_ib[-2]
            clis_penult = set(df_filtrado[df_filtrado['PERIODO_LIMPO'] == penultimo]['CODCLI'])
            clis_ultimo = set(df_filtrado[df_filtrado['PERIODO_LIMPO'] == ultimo_mes]['CODCLI'])
            ausentes    = clis_penult - clis_ultimo
            if ausentes:
                df_churn = (
                    df_filtrado[
                        (df_filtrado['CODCLI'].isin(ausentes)) &
                        (df_filtrado['PERIODO_LIMPO'] == penultimo)
                    ]
                    .groupby(['CODCLI', 'CLIENTE'])['TVENDA']
                    .sum()
                    .sort_values(ascending=False)
                    .reset_index()
                )
                col_fat = 'Fat. em ' + penultimo
                df_churn.columns = ['Codigo', 'Cliente', col_fat]
                df_churn[col_fat] = df_churn[col_fat].apply(fmt_brl)
                st.dataframe(df_churn, use_container_width=True, hide_index=True)
                st.caption(
                    str(len(ausentes)) + " clientes compraram em " +
                    penultimo + " e nao apareceram em " + ultimo_mes + "."
                )
            else:
                st.success("Todos os clientes de " + penultimo + " recompraram em " + ultimo_mes + ".")
        else:
            st.info("Selecione ao menos 2 meses para ativar a analise de churn.")

        st.markdown("---")

        st.write("### Ticket Medio por Rede de Clientes")
        df_ticket = (
            df_filtrado.groupby('REDE')
            .agg(Faturamento=('TVENDA', 'sum'), Pedidos=('CODCLI', 'count'))
            .reset_index()
        )
        df_ticket['Ticket Medio'] = (df_ticket['Faturamento'] / df_ticket['Pedidos']).apply(fmt_brl)
        df_ticket['Faturamento']  = df_ticket['Faturamento'].apply(fmt_brl)
        df_ticket['Pedidos']      = df_ticket['Pedidos'].apply(lambda x: f"{int(x):,}".replace(',', '.'))
        st.dataframe(
            df_ticket[['REDE', 'Ticket Medio', 'Faturamento', 'Pedidos']],
            use_container_width=True,
            hide_index=True
        )

        st.markdown("---")

        st.write("### Concentracao de Mix - Quantos SKUs cada cliente comprou")
        df_mix = (
            df_filtrado.groupby(['CODCLI', 'CLIENTE'])['CODPROD']
            .nunique()
            .sort_values(ascending=False)
            .reset_index()
        )
        df_mix.columns = ['Codigo', 'Cliente', 'SKUs Distintos']
        col_a, col_b = st.columns([2, 1])
        with col_a:
            st.dataframe(df_mix.head(30), use_container_width=True, hide_index=True)
        with col_b:
            st.metric("Media de SKUs / Cliente",   f"{df_mix['SKUs Distintos'].mean():.1f}")
            st.metric("Clientes com 1 SKU apenas", int((df_mix['SKUs Distintos'] == 1).sum()))
            st.metric("Clientes com 10+ SKUs",     int((df_mix['SKUs Distintos'] >= 10).sum()))

        st.markdown("---")

        st.write("### Exportar Analise Completa")
        buf_intel = io.BytesIO()
        with pd.ExcelWriter(buf_intel, engine='xlsxwriter') as w:
            df_evo = pd.DataFrame({'Periodo': colunas_meses_ib, 'Faturamento': serie_fat.values})
            df_evo.to_excel(w, index=False, sheet_name='Evolucao Mensal')
            top10_cli.to_excel(w, index=False, sheet_name='Top 10 Clientes')
            if not df_churn.empty:
                df_churn.to_excel(w, index=False, sheet_name='Risco Churn')
            df_ticket.to_excel(w, index=False, sheet_name='Ticket por Rede')
            df_mix.to_excel(w, index=False, sheet_name='Mix por Cliente')
        st.download_button(
            "Exportar Inteligencia de Negocio para Excel",
            data=buf_intel.getvalue(),
            file_name="rotina_8020_inteligencia.xlsx",
            mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
        )
