import streamlit as st
import pandas as pd
import numpy as np
import io
import datetime
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
NOME_MES_NUM = {v: k for k, v in ORDER_MESES.items()}

def delete_chave_cronologica(texto):
    try:
        m, a = str(texto).split('/')
        return (int(a), ORDER_MESES.get(m.lower(), 0))
    except Exception:
        return (99, 99)

def periodo_para_tupla(periodo_str):
    """Converte 'jun/26' em (2026, 6)"""
    try:
        m, a = str(periodo_str).split('/')
        return (2000 + int(a), ORDER_MESES.get(m.lower(), 0))
    except Exception:
        return None

def tupla_para_periodo(ano, mes):
    """Converte (2026, 6) em 'jun/26'"""
    return f"{NOME_MES_NUM.get(mes, '???')}/{str(ano)[-2:]}"

def somar_meses(ano, mes, n):
    """Soma n meses a partir de (ano, mes), retorna nova tupla (ano, mes)"""
    total = (ano * 12 + (mes - 1)) + n
    novo_ano = total // 12
    novo_mes = total % 12 + 1
    return (novo_ano, novo_mes)

def fmt_brl(valor):
    try:
        return "R$ " + f"{int(round(valor)):,}".replace(',', '.')
    except Exception:
        return "R$ 0"

def fmt_inteiro(valor):
    try:
        return f"{int(round(valor)):,}".replace(',', '.')
    except Exception:
        return "0"

def fmt_pct(valor):
    try:
        return f"{valor:.2f}%" if not pd.isna(valor) else "0.00%"
    except Exception:
        return "0.00%"

def fmt_var(valor):
    """Adiciona as setas e formata percentual"""
    try:
        if pd.isna(valor) or valor == float('inf') or valor == float('-inf'):
            return "-"
        if valor > 0:
            return f"\u25b2 +{valor:.2f}%"
        elif valor < 0:
            return f"\u25bc {valor:.2f}%"
        else:
            return "\u2796 0.00%"
    except Exception:
        return "-"

def style_var_color(val):
    """Aplica o CSS de cor Verde/Vermelho com base no valor numerico"""
    try:
        if pd.isna(val):
            return ''
        if val > 0:
            return 'color: #10b981; font-weight: bold;'
        if val < 0:
            return 'color: #ef4444; font-weight: bold;'
    except Exception:
        pass
    return ''

def aplicar_cor_variacao(styler, colunas):
    """Compat entre versoes do pandas (map vs applymap)"""
    if hasattr(styler, "map"):
        return styler.map(style_var_color, subset=colunas)
    return styler.applymap(style_var_color, subset=colunas)

def abrev_brl(valor):
    if pd.isna(valor) or valor == 0:
        return ""
    if valor >= 1_000_000:
        return f"R$ {valor/1_000_000:.1f}Mi".replace('.', ',')
    elif valor >= 1_000:
        return f"R$ {valor/1_000:.1f}K".replace('.', ',')
    else:
        return f"R$ {valor:.0f}"

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
anos_selecionados = st.sidebar.multiselect("Ano", anos_disponiveis)

df_temp = dados_originais[dados_originais['ANO_EIXO'].isin(anos_selecionados)] if anos_selecionados else dados_originais
todos_meses = sorted(df_temp['PERIODO_LIMPO'].unique(), key=delete_chave_cronologica)

meses_selecionados = st.sidebar.multiselect("Meses Disponiveis", todos_meses)
filiais_disponiveis = sorted(df_temp['CODFILIAL'].unique())

filial_sel = st.sidebar.multiselect("Unidade / Filial", filiais_disponiveis)
redes_disponiveis = sorted(df_temp['REDE'].dropna().unique())

rede_sel = st.sidebar.multiselect("Rede de Clientes", redes_disponiveis)
marcas_disponiveis = sorted(df_temp['MARCA'].dropna().unique()) if 'MARCA' in df_temp.columns else []

marca_sel = st.sidebar.multiselect("Marca do Produto", marcas_disponiveis)
busca_cliente = st.sidebar.text_input("Buscar por Nome do Cliente")
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

# ==============================================================================
# LÓGICA DE FILTRAGEM INTELIGENTE
# ==============================================================================
df_filtrado = dados_originais.copy()
df_filtrado_metas = dados_originais.copy() # Base cega para os filtros de data

# 1. Filtros de Data aplicados APENAS ao df_filtrado principal
if anos_selecionados:
    df_filtrado = df_filtrado[df_filtrado['ANO_EIXO'].isin(anos_selecionados)]
if meses_selecionados:
    df_filtrado = df_filtrado[df_filtrado['PERIODO_LIMPO'].isin(meses_selecionados)]

# 2. Função para aplicar os demais filtros em qualquer DataFrame
def aplicar_filtros_comerciais(df_alvo):
    res = df_alvo.copy()
    if filial_sel:
        res = res[res['CODFILIAL'].isin(filial_sel)]
    if rede_sel:
        res = res[res['REDE'].isin(rede_sel)]
    if marca_sel:
        res = res[res['MARCA'].isin(marca_sel)]
    if busca_cliente:
        res = res[res['CLIENTE'].str.contains(busca_cliente, case=False, na=False)]
    if busca_produto:
        res = res[res['DESCRICAO'].str.contains(busca_produto, case=False, na=False)]

    for campo, lista in [
        ('CODREDE', processar_lista_input(input_codrede)),
        ('CODCLI',  processar_lista_input(input_codcli)),
        ('CODPROD', processar_lista_input(input_codprod)),
        ('EAN',     processar_lista_input(input_ean)),
        ('NCM',     processar_lista_input(input_ncm)),
    ]:
        if lista and campo in res.columns:
            res = res[res[campo].astype(str).str.split('.').str[0].str.strip().isin(lista)]
            
    return res

# 3. Aplicando os filtros comerciais em ambas as bases
df_filtrado = aplicar_filtros_comerciais(df_filtrado)
df_filtrado_metas = aplicar_filtros_comerciais(df_filtrado_metas)


tab_clientes, tab_produtos, tab_inteligencia, tab_metas = st.tabs([
    "Clientes / Rede",
    "Produtos / Marca",
    "Inteligencia de Negocio",
    "Simulador de Metas"
])

# ---------------------------------------------------------------
# ABA 1 - CLIENTES
# ---------------------------------------------------------------
with tab_clientes:
    if df_filtrado.empty:
        st.warning("Sem dados para os filtros aplicados.")
    else:
        colunas_meses = sorted(df_filtrado['PERIODO_LIMPO'].unique(), key=delete_chave_cronologica)

        op_visao = st.radio("Metrica de Visualizacao Comercial (Aba Clientes)", ["Faturamento (R$)", "Volume (Caixas)"], horizontal=True)
        col_analise = 'TVENDA' if op_visao == "Faturamento (R$)" else 'QT'
        fmt_visao = fmt_brl if op_visao == "Faturamento (R$)" else fmt_inteiro

        tot_luc  = df_filtrado['TLUCRO'].sum() if 'TLUCRO' in df_filtrado.columns else 0
        tot_fat  = df_filtrado['TVENDA'].sum()
        tot_pos  = df_filtrado['CODCLI'].nunique()
        margem_g = (tot_luc / tot_fat * 100) if tot_fat > 0 else 0

        delta_str = None
        if len(colunas_meses) >= 2:
            mes_atual = colunas_meses[-1]
            mes_ant   = colunas_meses[-2]
            val_atual = df_filtrado[df_filtrado['PERIODO_LIMPO'] == mes_atual][col_analise].sum()
            val_ant   = df_filtrado[df_filtrado['PERIODO_LIMPO'] == mes_ant][col_analise].sum()
            if val_ant > 0:
                delta_val = (val_atual - val_ant) / val_ant * 100
                delta_str = f"{delta_val:+.1f}% vs {mes_ant}"

        st.write("### Indicadores Consolidados do Periodo")
        m1, m2, m3, m4 = st.columns(4)
        m1.metric(f"{op_visao} Total", fmt_visao(df_filtrado[col_analise].sum()), delta=delta_str)
        m2.metric("Lucro Bruto", fmt_brl(tot_luc))
        m3.metric("Clientes Positivados", f"{tot_pos:,}".replace(',', '.'))
        m4.metric("Margem de Contribuicao", fmt_pct(margem_g))
        st.markdown("---")

        resumo_temp = (
            df_filtrado.groupby('PERIODO_LIMPO')
            .agg(Faturamento=('TVENDA', 'sum'), Volume=('QT', 'sum'), Positivacoes=('CODCLI', 'nunique'))
            .reindex(colunas_meses)
            .fillna(0)
        )

        st.write("### Resumo de Desempenho Mensal")
        tabela_topo = {"Metrica": [f"Total {op_visao}", "Total Positivacoes"]}
        for m in colunas_meses:
            tabela_topo[m] = [
                fmt_visao(resumo_temp.loc[m, 'Faturamento' if col_analise == 'TVENDA' else 'Volume']),
                f"{int(resumo_temp.loc[m, 'Positivacoes']):,}".replace(',', '.'),
            ]
        df_resumo_mensal = pd.DataFrame(tabela_topo)
        st.dataframe(df_resumo_mensal, use_container_width=True, hide_index=True)

        st.write("### Analise de Evolucao Ano Contra Ano (YoY)")
        st.caption("Apresenta o volume absoluto ano a ano e a variacao em relacao ao mesmo periodo do ano anterior.")

        serie_periodo = (
            df_filtrado.groupby('PERIODO_LIMPO')[col_analise]
            .sum()
        )
        mapa_valores = {}
        for periodo, valor in serie_periodo.items():
            tup = periodo_para_tupla(periodo)
            if tup:
                mapa_valores[tup] = valor

        anos_presentes = sorted(set(a for a, m in mapa_valores.keys()))
        meses_nomes_ordenados = [NOME_MES_NUM[i] for i in range(1, 13)]

        linhas_yoy_vals = []
        for ano in anos_presentes:
            linha_val = {"Ano / Evolucao": str(ano)}
            for mes_num in range(1, 13):
                valor = mapa_valores.get((ano, mes_num))
                linha_val[NOME_MES_NUM[mes_num]] = valor if valor is not None else np.nan
            linhas_yoy_vals.append(linha_val)

        linhas_yoy_vars = []
        for i in range(1, len(anos_presentes)):
            ano_ant = anos_presentes[i-1]
            ano_atual = anos_presentes[i]
            linha_var = {"Ano / Evolucao": f"Evolucao {str(ano_atual)[-2:]} vs {str(ano_ant)[-2:]}"}
            for mes_num in range(1, 13):
                v_atual = mapa_valores.get((ano_atual, mes_num))
                v_ant = mapa_valores.get((ano_ant, mes_num))
                if v_atual is not None and v_ant is not None and v_ant > 0:
                    linha_var[NOME_MES_NUM[mes_num]] = (v_atual - v_ant) / v_ant * 100
                else:
                    linha_var[NOME_MES_NUM[mes_num]] = np.nan
            linhas_yoy_vars.append(linha_var)

        if linhas_yoy_vals:
            df_yoy_vals = pd.DataFrame(linhas_yoy_vals).set_index("Ano / Evolucao")
        else:
            df_yoy_vals = pd.DataFrame(columns=["Ano / Evolucao"] + meses_nomes_ordenados).set_index("Ano / Evolucao")

        if linhas_yoy_vars:
            df_yoy_vars = pd.DataFrame(linhas_yoy_vars).set_index("Ano / Evolucao")
        else:
            df_yoy_vars = pd.DataFrame(columns=["Ano / Evolucao"] + meses_nomes_ordenados).set_index("Ano / Evolucao")

        df_yoy_display = pd.DataFrame(index=df_yoy_vals.index.tolist() + df_yoy_vars.index.tolist(), columns=meses_nomes_ordenados)
        
        for c in meses_nomes_ordenados:
            df_yoy_display.loc[df_yoy_vals.index, c] = df_yoy_vals[c].apply(lambda x: fmt_visao(x) if pd.notnull(x) else "-")
            df_yoy_display.loc[df_yoy_vars.index, c] = df_yoy_vars[c].apply(lambda x: fmt_var(x) if pd.notnull(x) else "-")

        def color_yoy(val):
            if isinstance(val, str):
                if '▲' in val: return 'color: #10b981; font-weight: bold;'
                if '▼' in val: return 'color: #ef4444; font-weight: bold;'
            return ''

        if not df_yoy_display.empty:
            df_yoy_display.index.name = "Ano / Evolucao"
            df_yoy_display_reset = df_yoy_display.reset_index()
            style_yoy = df_yoy_display_reset.style
            if hasattr(style_yoy, "map"):
                style_yoy = style_yoy.map(color_yoy, subset=meses_nomes_ordenados)
            else:
                style_yoy = style_yoy.applymap(color_yoy, subset=meses_nomes_ordenados)
            
            st.dataframe(style_yoy, use_container_width=True, hide_index=True)
            df_yoy_excel = df_yoy_display_reset.copy()
        else:
            st.info("Sem dados suficientes para a analise YoY.")
            df_yoy_excel = pd.DataFrame()

        st.markdown("---")

        matrix_cli = (
            df_filtrado.pivot_table(
                index=['CODCLI', 'CLIENTE', 'CODREDE', 'REDE'],
                columns='PERIODO_LIMPO',
                values=col_analise,
                aggfunc='sum'
            )
            .fillna(0)
        )
        matrix_cli = matrix_cli.reindex(columns=colunas_meses, fill_value=0)
        matrix_cli['Historico Total'] = matrix_cli[colunas_meses].sum(axis=1)
        ult_3 = colunas_meses[-3:] if len(colunas_meses) >= 3 else colunas_meses
        matrix_cli['Media Ult. 3 Meses'] = matrix_cli[ult_3].mean(axis=1)

        matrix_cli = matrix_cli.sort_values('Historico Total', ascending=False).reset_index()
        matrix_cli = matrix_cli.rename(columns={'CODCLI': 'Codigo', 'CLIENTE': 'Cliente', 'CODREDE': 'Cod. Rede', 'REDE': 'Rede'})

        if len(colunas_meses) >= 2:
            mes_atual = colunas_meses[-1]
            mes_ant   = colunas_meses[-2]
            matrix_cli['Var. Ult. Mes'] = ((matrix_cli[mes_atual] - matrix_cli[mes_ant]) / matrix_cli[mes_ant].replace(0, np.nan)) * 100
        else:
            matrix_cli['Var. Ult. Mes'] = np.nan

        if len(colunas_meses) >= 4:
            mes_atual = colunas_meses[-1]
            meses_base_3m = colunas_meses[-4:-1]  
            media_3m_base = matrix_cli[meses_base_3m].mean(axis=1)
            matrix_cli['Var. vs Media 3M'] = ((matrix_cli[mes_atual] - media_3m_base) / media_3m_base.replace(0, np.nan)) * 100
        elif len(colunas_meses) >= 2:
            mes_atual = colunas_meses[-1]
            meses_base_3m = colunas_meses[:-1]
            media_3m_base = matrix_cli[meses_base_3m].mean(axis=1)
            matrix_cli['Var. vs Media 3M'] = ((matrix_cli[mes_atual] - media_3m_base) / media_3m_base.replace(0, np.nan)) * 100
        else:
            matrix_cli['Var. vs Media 3M'] = np.nan

        matrix_cli['Acumulado'] = matrix_cli['Historico Total'].cumsum()
        soma_v = matrix_cli['Historico Total'].sum()
        matrix_cli['Pct Acumulado'] = (matrix_cli['Acumulado'] / soma_v * 100) if soma_v > 0 else 0
        matrix_cli['Curva ABC'] = matrix_cli['Pct Acumulado'].apply(
            lambda x: 'A' if x <= 80 else ('B' if x <= 95 else 'C')
        )

        colunas_exib = (
            ['Curva ABC', 'Cod. Rede', 'Rede', 'Codigo', 'Cliente']
            + colunas_meses
            + ['Var. Ult. Mes', 'Var. vs Media 3M', 'Media Ult. 3 Meses', 'Historico Total']
        )
        cols_num = colunas_meses + ['Media Ult. 3 Meses', 'Historico Total']
        cols_var = ['Var. Ult. Mes', 'Var. vs Media 3M']

        st.write("### Grade de Resultados por Cliente e Rede")

        format_dict = {c: fmt_visao for c in cols_num}
        for c in cols_var:
            format_dict[c] = fmt_var

        style_grid = matrix_cli[colunas_exib].style.format(format_dict)
        style_grid = aplicar_cor_variacao(style_grid, cols_var)

        st.dataframe(
            style_grid,
            use_container_width=True,
            height=450,
            hide_index=True
        )

        colunas_excel_resumo = ['Metrica'] + colunas_meses
        df_resumo_excel = df_resumo_mensal[colunas_excel_resumo].copy()
        df_resumo_excel = pd.concat(
            [pd.DataFrame(columns=['Curva ABC', 'Cod. Rede', 'Rede', 'Codigo']), df_resumo_excel],
            axis=1
        ).fillna('')

        matrix_cli_excel = matrix_cli[colunas_exib].copy()
        for c in cols_var:
            matrix_cli_excel[c] = matrix_cli_excel[c].apply(fmt_var)

        linha_total = {}
        for c in colunas_exib:
            if c in cols_num:
                linha_total[c] = matrix_cli[c].sum()
            elif c in cols_var:
                linha_total[c] = ''
            else:
                linha_total[c] = ''
        linha_total['Cliente'] = 'TOTAL GERAL'
        df_total_linha = pd.DataFrame([linha_total])
        for c in cols_num:
            df_total_linha[c] = df_total_linha[c].apply(fmt_visao)
        matrix_cli_excel = pd.concat([matrix_cli_excel, df_total_linha], ignore_index=True)

        buf = io.BytesIO()
        with pd.ExcelWriter(buf, engine='xlsxwriter') as w:
            startrow = 0
            df_resumo_excel.to_excel(w, index=False, sheet_name='Clientes 8020', startrow=startrow)
            startrow += len(df_resumo_excel) + 2

            if not df_yoy_excel.empty:
                ws_label = pd.DataFrame([{"Ano": "Analise de Evolucao YoY"}])
                ws_label.to_excel(w, index=False, sheet_name='Clientes 8020', startrow=startrow, header=False)
                startrow += 1
                df_yoy_excel.to_excel(w, index=False, sheet_name='Clientes 8020', startrow=startrow)
                startrow += len(df_yoy_excel) + 2

            matrix_cli_excel.to_excel(w, index=False, sheet_name='Clientes 8020', startrow=startrow)

        st.download_button(
            "Exportar Analise de Clientes para Excel",
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
        op_visao_prod = st.radio("Metrica de Visualizacao Comercial (Aba Produtos)", ["Faturamento (R$)", "Volume (Caixas)"], horizontal=True, key="op_visao_prod")
        col_analise_prod = 'TVENDA' if op_visao_prod == "Faturamento (R$)" else 'QT'
        fmt_visao_prod = fmt_brl if op_visao_prod == "Faturamento (R$)" else fmt_inteiro

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
            .sort_values(col_analise_prod, ascending=False)
            .reset_index()
        )
        df_prod['Acumulado'] = df_prod[col_analise_prod].cumsum()
        soma_p = df_prod[col_analise_prod].sum()
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
            height=400,
            hide_index=True
        )

        df_var_marca_export = pd.DataFrame()

        if 'MARCA' in df_filtrado.columns:
            st.write(f"### Participacao de {op_visao_prod.split(' ')[0]} por Marca (Top 10)")
            colunas_meses_prod = sorted(df_filtrado['PERIODO_LIMPO'].unique(), key=delete_chave_cronologica)
            top10_marcas = (
                df_filtrado.groupby('MARCA')[col_analise_prod].sum().sort_values(ascending=False).head(10).index.tolist()
            )
            df_evo_marca = (
                df_filtrado[df_filtrado['MARCA'].isin(top10_marcas)]
                .pivot_table(index='MARCA', columns='PERIODO_LIMPO', values=col_analise_prod, aggfunc='sum')
                .reindex(columns=colunas_meses_prod, fill_value=0)
            )

            df_evo_marca['Total'] = df_evo_marca.sum(axis=1)
            df_evo_hm = df_evo_marca.sort_values('Total', ascending=True).drop(columns=['Total'])

            z_data = df_evo_hm.values
            text_data = [[abrev_brl(val) if col_analise_prod == 'TVENDA' else f"{val/1000:.1f}K".replace('.', ',') if val >= 1000 else f"{val:.0f}" for val in row] for row in z_data]

            fig_hm = go.Figure(data=go.Heatmap(
                z=z_data,
                x=colunas_meses_prod,
                y=df_evo_hm.index,
                text=text_data,
                texttemplate="%{text}",
                colorscale='Blues',
                showscale=False,
                hovertemplate='<b>%{y}</b><br>%{x}<br>' + ('R$ %{z:,.2f}' if col_analise_prod == 'TVENDA' else '%{z:,.0f} Caixas') + '<extra></extra>'
            ))
            layout_hm = base_layout(450)
            layout_hm['xaxis'].update(showgrid=False, zeroline=False)
            layout_hm['yaxis'].update(showgrid=False, zeroline=False)
            fig_hm.update_layout(**layout_hm)
            st.plotly_chart(fig_hm, use_container_width=True)

            ultimos_6m_prod = colunas_meses_prod[-6:] if len(colunas_meses_prod) >= 6 else colunas_meses_prod
            if len(colunas_meses_prod) >= 1:
                st.write("### Variacao das Principais Marcas (Top 10)")
                mes_atual_p = colunas_meses_prod[-1]
                tup_atual = periodo_para_tupla(mes_atual_p)
                mes_yoy = tupla_para_periodo(tup_atual[0]-1, tup_atual[1]) if tup_atual else None

                df_var_marca = df_evo_marca.sort_values('Total', ascending=False).drop(columns=['Total'])
                df_var_marca = df_var_marca[ultimos_6m_prod].copy().reset_index()

                media_6m = df_var_marca[ultimos_6m_prod].mean(axis=1)
                df_var_marca['Var. vs Media 6M'] = ((df_var_marca[mes_atual_p] - media_6m) / media_6m.replace(0, np.nan)) * 100

                if mes_yoy in colunas_meses_prod:
                    val_atual = df_evo_marca.loc[df_var_marca['MARCA'], mes_atual_p]
                    val_yoy = df_evo_marca.loc[df_var_marca['MARCA'], mes_yoy]
                    df_var_marca['Var. YoY'] = ((val_atual.values - val_yoy.values) / val_yoy.replace(0, np.nan).values) * 100
                else:
                    df_var_marca['Var. YoY'] = np.nan

                cols_fmt_m = {c: (fmt_brl if col_analise_prod == 'TVENDA' else fmt_inteiro) for c in ultimos_6m_prod}
                cols_fmt_m['Var. vs Media 6M'] = fmt_var
                cols_fmt_m['Var. YoY'] = fmt_var

                style_var_m = df_var_marca.style.format(cols_fmt_m)
                style_var_m = aplicar_cor_variacao(style_var_m, ['Var. vs Media 6M', 'Var. YoY'])
                st.dataframe(style_var_m, use_container_width=True, hide_index=True)

                df_var_marca_export = df_var_marca.copy()
                for c in ultimos_6m_prod:
                    df_var_marca_export[c] = df_var_marca_export[c].apply(fmt_brl if col_analise_prod == 'TVENDA' else fmt_inteiro)
                df_var_marca_export['Var. vs Media 6M'] = df_var_marca_export['Var. vs Media 6M'].apply(fmt_var)
                df_var_marca_export['Var. YoY'] = df_var_marca_export['Var. YoY'].apply(fmt_var)

        buf_p = io.BytesIO()
        with pd.ExcelWriter(buf_p, engine='xlsxwriter') as w:
            df_prod[base_cols].to_excel(w, index=False, sheet_name='Produtos 8020')
            if not df_var_marca_export.empty:
                df_var_marca_export.to_excel(w, index=False, sheet_name='Top 10 Marcas')

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
        op_visao_intel = st.radio("Metrica de Visualizacao Comercial (Aba Inteligencia)", ["Faturamento (R$)", "Volume (Caixas)"], horizontal=True, key="op_visao_intel")
        col_analise_intel = 'TVENDA' if op_visao_intel == "Faturamento (R$)" else 'QT'
        fmt_visao_intel = fmt_brl if op_visao_intel == "Faturamento (R$)" else fmt_inteiro

        colunas_meses_ib = sorted(df_filtrado['PERIODO_LIMPO'].unique(), key=delete_chave_cronologica)

        st.write(f"### Evolucao de {op_visao_intel} Mensal")
        serie_fat = (
            df_filtrado.groupby('PERIODO_LIMPO')[col_analise_intel]
            .sum()
            .reindex(colunas_meses_ib)
            .fillna(0)
        )
        fat_fmt_list = [fmt_visao_intel(v) for v in serie_fat.values]
        fig_fat = go.Figure(go.Scatter(
            x=serie_fat.index.tolist(),
            y=serie_fat.values,
            mode='lines+markers',
            line=dict(color='#3b82f6', width=2),
            marker=dict(size=7, color='#60a5fa'),
            fill='tozeroy',
            fillcolor='rgba(59,130,246,0.10)',
            hovertemplate='<b>%{x}</b><br>' + f'{op_visao_intel.split(" ")[0]}: %{{customdata}}<extra></extra>',
            customdata=fat_fmt_list,
        ))
        layout_fat = base_layout(360)
        if col_analise_intel == 'TVENDA':
            layout_fat['yaxis'] = dict(gridcolor=PLOT_GRID, tickformat=',', tickprefix='R$ ')
        else:
            layout_fat['yaxis'] = dict(gridcolor=PLOT_GRID, tickformat=',')
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
            serie_fat_para_margem = (
                df_filtrado.groupby('PERIODO_LIMPO')['TVENDA']
                .sum()
                .reindex(colunas_meses_ib)
                .fillna(0)
            )
            serie_margem = (serie_luc_m / serie_fat_para_margem * 100).fillna(0)
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

        st.write(f"### Top 10 Clientes por {op_visao_intel.split(' ')[0]}")
        top10_cli = (
            df_filtrado.groupby(['CODCLI', 'CLIENTE'])[col_analise_intel]
            .sum()
            .sort_values(ascending=False)
            .head(10)
            .reset_index()
        )
        lbl_metrica = 'Faturamento' if col_analise_intel == 'TVENDA' else 'Volume'
        top10_cli.columns = ['Codigo', 'Cliente', lbl_metrica]
        lbl_fmt = 'Faturamento R$' if col_analise_intel == 'TVENDA' else 'Volume (Caixas)'
        top10_cli[lbl_fmt] = top10_cli[lbl_metrica].apply(fmt_visao_intel)
        soma_top = top10_cli[lbl_metrica].sum()
        top10_cli['% do Total'] = top10_cli[lbl_metrica].apply(
            lambda x: fmt_pct(x / soma_top * 100) if soma_top > 0 else '0.00%'
        )
        st.dataframe(
            top10_cli[['Codigo', 'Cliente', lbl_fmt, '% do Total']],
            use_container_width=True,
            hide_index=True
        )
        top10_plot = top10_cli.sort_values(lbl_metrica, ascending=True)
        fig_top10 = go.Figure(go.Bar(
            x=top10_plot[lbl_metrica],
            y=top10_plot['Cliente'],
            orientation='h',
            marker_color='#6366f1',
            text=top10_plot[lbl_fmt],
            textposition='outside',
            hovertemplate='<b>%{y}</b><br>' + f'{lbl_metrica}: %{{customdata}}<extra></extra>',
            customdata=top10_plot[lbl_fmt],
        ))
        layout_top10 = base_layout(400)
        layout_top10['xaxis'] = dict(gridcolor=PLOT_GRID, showticklabels=False, tickvals=[])
        layout_top10['yaxis'] = dict(gridcolor=PLOT_GRID)
        layout_top10['margin'] = dict(l=10, r=150, t=40, b=10)
        fig_top10.update_layout(**layout_top10)
        st.plotly_chart(fig_top10, use_container_width=True)

        st.markdown("---")

        st.write(f"### Risco de Churn - Clientes que nao compraram no ultimo mes (com base em {op_visao_intel.split(' ')[0]})")
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
                    .groupby(['CODCLI', 'CLIENTE'])[col_analise_intel]
                    .sum()
                    .sort_values(ascending=False)
                    .reset_index()
                )
                col_fat = ('Fat. em ' if col_analise_intel == 'TVENDA' else 'Vol. em ') + penultimo
                df_churn.columns = ['Codigo', 'Cliente', col_fat]
                df_churn[col_fat] = df_churn[col_fat].apply(fmt_visao_intel)
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
            col_excel_lbl = 'Faturamento' if col_analise_intel == 'TVENDA' else 'Volume'
            pd.DataFrame({"Periodo": colunas_meses_ib, col_excel_lbl: serie_fat.values}).to_excel(
                w, index=False, sheet_name="Evolucao Mensal"
            )
            
            df_top10_excel = top10_cli.copy()
            df_top10_excel.to_excel(w, index=False, sheet_name="Top 10 Clientes")
            
            if not df_churn.empty:
                df_churn.to_excel(w, index=False, sheet_name="Risco Churn")
            df_ticket.to_excel(w, index=False, sheet_name="Ticket por Rede")
            df_mix.to_excel(w, index=False, sheet_name="Mix por Cliente")
        st.download_button(
            "Exportar Inteligencia de Negocio para Excel",
            data=buf_intel.getvalue(),
            file_name="rotina_8020_inteligencia.xlsx",
            mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
        )

# ---------------------------------------------------------------
# ABA 4 - SIMULADOR DE METAS
# ---------------------------------------------------------------
with tab_metas:
    if df_filtrado_metas.empty:
        st.warning("Sem dados para simular metas com os filtros aplicados (verifique se os filtros de cliente/produto nao excluiram tudo).")
    else:
        st.write("## Simulador de Metas Comerciais")
        st.caption(
            "Defina metas de crescimento por Rede, Cliente ou Produto/Marca, em Faturamento ou Volume. "
            "As metas de Rede sao quebradas automaticamente entre os clientes da rede, proporcionalmente "
            "ao historico de cada um."
        )

        df_metas_base = df_filtrado_metas.copy()

        # =========================================================
        # 1. DETERMINAR MES VIGENTE E PERIODOS DISPONIVEIS
        # =========================================================
        hoje = datetime.date.today()
        ano_vigente, mes_vigente = hoje.year, hoje.month
        periodo_vigente_tupla = (ano_vigente, mes_vigente)
        periodo_vigente_str = tupla_para_periodo(ano_vigente, mes_vigente)

        todos_periodos_base = sorted(df_metas_base['PERIODO_LIMPO'].unique(), key=delete_chave_cronologica)
        tuplas_disponiveis = sorted(
            [t for t in (periodo_para_tupla(p) for p in todos_periodos_base) if t is not None]
        )

        if not tuplas_disponiveis:
            st.warning("Nao foi possivel identificar periodos validos na base.")
        else:
            ultimo_periodo_dados = tuplas_disponiveis[-1]

            # =====================================================
            # 2. SELECAO DO PERIODO DA META
            # =====================================================
            st.write("### 1. Periodo da Meta")

            opcoes_periodo_meta = {
                "Mes Vigente (" + periodo_vigente_str + ")": (periodo_vigente_tupla, periodo_vigente_tupla),
                "Proximo Mes (" + tupla_para_periodo(*somar_meses(*periodo_vigente_tupla, 1)) + ")":
                    (somar_meses(*periodo_vigente_tupla, 1), somar_meses(*periodo_vigente_tupla, 1)),
                "Proximo Trimestre": (
                    somar_meses(*periodo_vigente_tupla, 1),
                    somar_meses(*periodo_vigente_tupla, 3)
                ),
                "Proximo Semestre": (
                    somar_meses(*periodo_vigente_tupla, 1),
                    somar_meses(*periodo_vigente_tupla, 6)
                ),
                "Periodo Customizado": None,
            }

            col_p1, col_p2 = st.columns([2, 1])
            with col_p1:
                escolha_periodo = st.selectbox("Selecione o periodo alvo da meta", list(opcoes_periodo_meta.keys()))

            if escolha_periodo == "Periodo Customizado":
                with col_p2:
                    n_meses_custom = st.number_input("Quantidade de meses a frente", min_value=1, max_value=24, value=1)
                inicio_meta = somar_meses(*periodo_vigente_tupla, 1)
                fim_meta = somar_meses(*periodo_vigente_tupla, int(n_meses_custom))
            else:
                inicio_meta, fim_meta = opcoes_periodo_meta[escolha_periodo]

            periodos_meta_tuplas = []
            cursor = inicio_meta
            while cursor <= fim_meta:
                periodos_meta_tuplas.append(cursor)
                if cursor == fim_meta:
                    break
                cursor = somar_meses(*cursor, 1)
            periodos_meta_str = [tupla_para_periodo(a, m) for a, m in periodos_meta_tuplas]
            n_meses_meta = len(periodos_meta_tuplas)

            st.info(
                "Periodo da meta: **" + (periodos_meta_str[0] if periodos_meta_str else "-") +
                ("" if n_meses_meta <= 1 else " ate " + periodos_meta_str[-1]) +
                "** (" + str(n_meses_meta) + " mes(es))"
            )

            # =====================================================
            # 3. SELECAO DA BASE DE COMPARACAO
            # =====================================================
            st.write("### 2. Base de Comparacao")

            sugestao_base = "Mesmo Periodo no Ano Anterior"

            opcoes_base = [
                "Mesmo Periodo no Ano Anterior",
                "Media dos Ultimos 3 Meses",
                "Media dos Ultimos 6 Meses",
            ]
            idx_sugestao = opcoes_base.index(sugestao_base)
            base_comparacao = st.selectbox(
                "Base de comparacao (sugestao automatica selecionada; pode trocar)",
                opcoes_base,
                index=idx_sugestao
            )

            def obter_periodos_base(periodos_meta_tuplas, base_comparacao, ultimo_periodo_dados):
                if base_comparacao == "Mesmo Periodo no Ano Anterior":
                    return [(a - 1, m) for a, m in periodos_meta_tuplas]
                elif base_comparacao == "Media dos Ultimos 3 Meses":
                    fim = ultimo_periodo_dados
                    base = []
                    cursor = fim
                    for _ in range(3):
                        base.append(cursor)
                        cursor = somar_meses(*cursor, -1)
                    return sorted(base)
                else: 
                    fim = ultimo_periodo_dados
                    base = []
                    cursor = fim
                    for _ in range(6):
                        base.append(cursor)
                        cursor = somar_meses(*cursor, -1)
                    return sorted(base)

            periodos_base_tuplas = obter_periodos_base(periodos_meta_tuplas, base_comparacao, ultimo_periodo_dados)
            periodos_base_str = [tupla_para_periodo(a, m) for a, m in periodos_base_tuplas]

            st.caption("Periodos usados como base: " + ", ".join(periodos_base_str))

            st.markdown("---")

            # =====================================================
            # 4. PAINEL HISTORICO DE REFERENCIA
            # =====================================================
            st.write("### 3. Historico de Referencia")
            st.caption("Ultimos 6 meses de dados contados a partir do mes passado, mais o periodo do ano anterior referenciado para a meta.")

            mes_passado_tupla = somar_meses(ano_vigente, mes_vigente, -1)
            ultimos_6_tuplas = [somar_meses(*mes_passado_tupla, -i) for i in range(6)]
            ultimos_6_tuplas.sort()
            colunas_hist_6m = [tupla_para_periodo(a, m) for a, m in ultimos_6_tuplas]

            periodos_meta_ano_ant = [(a - 1, m) for a, m in periodos_meta_tuplas]
            periodos_meta_ano_ant_str = [tupla_para_periodo(a, m) for a, m in periodos_meta_ano_ant]
            col_ano_ant_nome = f"Ref. Ano Ant. ({'+'.join(periodos_meta_ano_ant_str)})"

            nivel_meta = st.radio(
                "Nivel de definicao da meta",
                ["Rede de Clientes", "Cliente Individual", "Produto / Marca", "Produto Individual"],
                horizontal=True
            )

            metrica_meta = st.radio(
                "Metrica base para a meta",
                ["Faturamento (R$)", "Volume (Caixas)"],
                horizontal=True
            )
            col_metrica = 'TVENDA' if metrica_meta == "Faturamento (R$)" else 'QT'
            fmt_metrica = fmt_brl if metrica_meta == "Faturamento (R$)" else fmt_inteiro

            # =====================================================
            # 5. CONSTRUCAO DA TABELA DE HISTORICO + DEFINICAO DE META
            # =====================================================
            if nivel_meta == "Rede de Clientes":
                chave_cols = ['CODREDE', 'REDE']
                nome_chave = 'REDE'
            elif nivel_meta == "Cliente Individual":
                chave_cols = ['CODCLI', 'CLIENTE']
                nome_chave = 'CLIENTE'
            elif nivel_meta == "Produto Individual":
                chave_cols = ['CODPROD', 'DESCRICAO']
                nome_chave = 'DESCRICAO'
            else:
                chave_cols = ['MARCA']
                nome_chave = 'MARCA'

            pivot_hist = (
                df_metas_base.pivot_table(
                    index=chave_cols,
                    columns='PERIODO_LIMPO',
                    values=col_metrica,
                    aggfunc='sum'
                )
                .fillna(0)
            )

            colunas_disponiveis_6m = [c for c in colunas_hist_6m if c in pivot_hist.columns]
            pivot_hist_exib = pivot_hist.reindex(columns=colunas_disponiveis_6m, fill_value=0).copy()
            
            cols_ref_ant = [c for c in periodos_meta_ano_ant_str if c in pivot_hist.columns]
            if cols_ref_ant:
                pivot_hist_exib[col_ano_ant_nome] = pivot_hist[cols_ref_ant].sum(axis=1)
            else:
                pivot_hist_exib[col_ano_ant_nome] = 0

            # --- CORRECAO CRUCIAL DA BASE MATEMATICA ---
            colunas_base_disponiveis = [c for c in periodos_base_str if c in pivot_hist.columns]
            if colunas_base_disponiveis:
                if base_comparacao == "Mesmo Periodo no Ano Anterior":
                    valor_base_serie = pivot_hist[colunas_base_disponiveis].sum(axis=1)
                else:
                    valor_base_serie = pivot_hist[colunas_base_disponiveis].mean(axis=1) * n_meses_meta
            else:
                valor_base_serie = pd.Series(0, index=pivot_hist.index)

            col_base_meta = 'Base p/ Meta (' + base_comparacao + ')'
            pivot_hist_exib[col_base_meta] = valor_base_serie
            pivot_hist_exib = pivot_hist_exib.sort_values(col_base_meta, ascending=False)
            pivot_hist_exib = pivot_hist_exib.reset_index()

            if nivel_meta == "Rede de Clientes":
                pivot_hist_exib = pivot_hist_exib.rename(columns={'CODREDE': 'Codigo', 'REDE': 'Nome'})
                col_nome_exib = 'Nome'
            elif nivel_meta == "Cliente Individual":
                pivot_hist_exib = pivot_hist_exib.rename(columns={'CODCLI': 'Codigo', 'CLIENTE': 'Nome'})
                col_nome_exib = 'Nome'
            elif nivel_meta == "Produto Individual":
                pivot_hist_exib = pivot_hist_exib.rename(columns={'CODPROD': 'Codigo', 'DESCRICAO': 'Nome'})
                col_nome_exib = 'Nome'
            else:
                pivot_hist_exib = pivot_hist_exib.rename(columns={'MARCA': 'Nome'})
                col_nome_exib = 'Nome'

            pivot_hist_exib_top = pivot_hist_exib.copy()

            st.write("#### Historico (somente leitura)")
            cols_fmt_hist = colunas_disponiveis_6m + [col_ano_ant_nome, col_base_meta]
            
            def style_destaque_base(styler):
                cols_destaque = [c for c in cols_fmt_hist if c in periodos_base_str or c == col_base_meta]
                if cols_destaque:
                    return styler.set_properties(subset=cols_destaque, **{'background-color': '#1e293b', 'color': '#38bdf8', 'font-weight': 'bold'})
                return styler

            style_hist = pivot_hist_exib_top.style.format({c: fmt_metrica for c in cols_fmt_hist})
            style_hist = style_destaque_base(style_hist)

            st.dataframe(
                style_hist,
                use_container_width=True,
                height=350,
                hide_index=True
            )

            st.markdown("---")

            # =====================================================
            # 6. DEFINICAO DA META (SINCRONIZADA COM SESSION STATE)
            # =====================================================
            st.write("### 4. Definicao da Meta")
            st.caption(
                "Edite o **Crescimento %** OU o **Valor Absoluto** diretamente na tabela. A alteração de um refletirá automaticamente no outro."
            )

            chave_session_data = f"metas_data_{nivel_meta}_{metrica_meta}_{escolha_periodo}_{base_comparacao}"

            # Inicializa a tabela no Session State apenas uma vez para esta configuração
            if chave_session_data not in st.session_state:
                df_editor_init = pd.DataFrame({
                    'Codigo': pivot_hist_exib_top['Codigo'] if 'Codigo' in pivot_hist_exib_top.columns else pivot_hist_exib_top[col_nome_exib],
                    'Nome': pivot_hist_exib_top[col_nome_exib],
                    'Base Historica': pivot_hist_exib_top[col_base_meta],
                    'Base Fmt': pivot_hist_exib_top[col_base_meta].apply(fmt_metrica),
                    'Crescimento %': [0.0] * len(pivot_hist_exib_top),
                    'Valor Absoluto Meta': pivot_hist_exib_top[col_base_meta].round(2),
                })
                st.session_state[chave_session_data] = df_editor_init

            # Controle para aplicar lote
            col_input1, col_input2, _ = st.columns([2, 2, 4])
            with col_input1:
                pct_lote = st.number_input("Aplicar % de cresc. em lote:", value=0.0, step=1.0, format="%.2f")
            with col_input2:
                st.write("") # alinhamento visual
                if st.button("Aplicar Lote na Tabela"):
                    st.session_state[chave_session_data]['Crescimento %'] = pct_lote
                    st.session_state[chave_session_data]['Valor Absoluto Meta'] = (
                        st.session_state[chave_session_data]['Base Historica'] * (1 + pct_lote / 100)
                    ).round(2)
                    st.rerun()

            # Callback para sincronizar celulas de % e Valor ao vivo
            def sync_editor():
                edited = st.session_state[f"ui_editor_{chave_session_data}"]
                df = st.session_state[chave_session_data]
                for idx_str, changes in edited['edited_rows'].items():
                    idx = int(idx_str)
                    base = df.at[idx, 'Base Historica']
                    
                    if 'Crescimento %' in changes:
                        new_pct = changes['Crescimento %']
                        df.at[idx, 'Crescimento %'] = new_pct
                        df.at[idx, 'Valor Absoluto Meta'] = round(base * (1 + new_pct / 100), 2)
                    elif 'Valor Absoluto Meta' in changes:
                        new_val = changes['Valor Absoluto Meta']
                        df.at[idx, 'Valor Absoluto Meta'] = new_val
                        df.at[idx, 'Crescimento %'] = round(((new_val - base) / base * 100), 2) if base != 0 else 0

            st.data_editor(
                st.session_state[chave_session_data],
                key=f"ui_editor_{chave_session_data}",
                on_change=sync_editor,
                disabled=['Codigo', 'Nome', 'Base Fmt', 'Base Historica'],
                column_config={
                    'Base Historica': None, # Ocultamos a base float, deixamos apenas a formatada abaixo
                    'Base Fmt': st.column_config.TextColumn("Base Histórica", disabled=True),
                    'Crescimento %': st.column_config.NumberColumn("Crescimento %", format="%.2f%%", step=1.0),
                    'Valor Absoluto Meta': st.column_config.NumberColumn("Valor Meta (Absoluto)", format="%.2f", step=100.0),
                },
                use_container_width=True,
                height=400,
                hide_index=True
            )

            # Extraimos o dataframe final para os calculos abaixo
            df_editado = st.session_state[chave_session_data].copy()
            df_editado['Meta Final'] = df_editado['Valor Absoluto Meta']

            # =====================================================
            # 7. QUEBRA HIERARQUICA: REDE -> CLIENTES
            # =====================================================
            df_quebra_cliente = pd.DataFrame()
            if nivel_meta == "Rede de Clientes":
                st.markdown("---")
                st.write("### 5. Quebra da Meta por Cliente (dentro de cada Rede)")
                st.caption(
                    "A meta definida por rede e distribuida entre os clientes daquela rede, "
                    "proporcionalmente ao historico de participacao de cada cliente na base escolhida."
                )

                linhas_quebra = []
                for _, linha_rede in df_editado.iterrows():
                    cod_rede = linha_rede['Codigo']
                    meta_rede = linha_rede['Meta Final']

                    clientes_da_rede = df_metas_base[df_metas_base['CODREDE'] == cod_rede][['CODCLI', 'CLIENTE']].drop_duplicates()
                    if clientes_da_rede.empty:
                        continue

                    hist_clientes = (
                        df_metas_base[
                            (df_metas_base['CODREDE'] == cod_rede) &
                            (df_metas_base['PERIODO_LIMPO'].isin(colunas_base_disponiveis))
                        ]
                        .groupby(['CODCLI', 'CLIENTE'])[col_metrica]
                        .sum()
                        .div(max(len(colunas_base_disponiveis), 1))
                    )

                    soma_hist_rede = hist_clientes.sum()
                    for (cod_cli, nome_cli), valor_hist in hist_clientes.items():
                        participacao = (valor_hist / soma_hist_rede) if soma_hist_rede > 0 else (1 / len(hist_clientes))
                        meta_cliente = meta_rede * participacao
                        linhas_quebra.append({
                            'Cod. Rede': cod_rede,
                            'Rede': linha_rede['Nome'],
                            'Codigo Cliente': cod_cli,
                            'Cliente': nome_cli,
                            'Base Historica Cliente': valor_hist,
                            'Participacao na Rede %': participacao * 100,
                            'Meta Cliente': meta_cliente,
                        })

                if linhas_quebra:
                    df_quebra_cliente = pd.DataFrame(linhas_quebra)
                    st.dataframe(
                        df_quebra_cliente.style.format({
                            'Base Historica Cliente': fmt_metrica,
                            'Participacao na Rede %': fmt_pct,
                            'Meta Cliente': fmt_metrica,
                        }),
                        use_container_width=True,
                        height=350,
                        hide_index=True
                    )
                else:
                    st.info("Defina metas com crescimento diferente de zero para visualizar a quebra por cliente.")

            st.markdown("---")

            # =====================================================
            # 8. RESUMO CONSOLIDADO DA META
            # =====================================================
            st.write("### Resumo da Meta")
            soma_base_total = df_editado['Base Historica'].sum()
            soma_meta_total = df_editado['Meta Final'].sum()
            crescimento_total = ((soma_meta_total - soma_base_total) / soma_base_total * 100) if soma_base_total > 0 else 0

            rc1, rc2, rc3 = st.columns(3)
            rc1.metric("Base Historica Total", fmt_metrica(soma_base_total))
            rc2.metric("Meta Total Definida", fmt_metrica(soma_meta_total))
            rc3.metric("Crescimento Implicito", fmt_pct(crescimento_total))

            df_grafico_meta = df_editado.sort_values('Meta Final', ascending=False).head(15)
            fig_meta = go.Figure()
            fig_meta.add_trace(go.Bar(
                name='Base Historica',
                y=df_grafico_meta['Nome'],
                x=df_grafico_meta['Base Historica'],
                orientation='h',
                marker_color='#475569',
                hovertemplate='<b>%{y}</b><br>Base: %{x:,.0f}<extra></extra>',
            ))
            fig_meta.add_trace(go.Bar(
                name='Meta Definida',
                y=df_grafico_meta['Nome'],
                x=df_grafico_meta['Meta Final'],
                orientation='h',
                marker_color='#3b82f6',
                hovertemplate='<b>%{y}</b><br>Meta: %{x:,.0f}<extra></extra>',
            ))
            layout_meta = base_layout(450)
            layout_meta['barmode'] = 'group'
            layout_meta['legend'] = dict(orientation='h', yanchor='bottom', y=1.02, xanchor='right', x=1)
            layout_meta['yaxis'] = dict(gridcolor=PLOT_GRID, autorange='reversed')
            fig_meta.update_layout(**layout_meta)
            st.plotly_chart(fig_meta, use_container_width=True)

            # =====================================================
            # 9. EXPORTACAO PARA EXCEL
            # =====================================================
            st.markdown("---")
            st.write("### Exportar Meta para Excel")
            st.caption("Gera uma planilha pronta para envio, com o resumo, o detalhamento por item e a quebra por cliente (se aplicavel).")

            df_export_resumo = pd.DataFrame({
                'Campo': [
                    'Nivel da Meta', 'Metrica', 'Periodo da Meta', 'Base de Comparacao',
                    'Periodos Base Utilizados', 'Base Historica Total', 'Meta Total Definida',
                    'Crescimento Implicito Total'
                ],
                'Valor': [
                    nivel_meta, metrica_meta,
                    (periodos_meta_str[0] if periodos_meta_str else '-') + (
                        '' if n_meses_meta <= 1 else ' ate ' + periodos_meta_str[-1]
                    ),
                    base_comparacao,
                    ", ".join(periodos_base_str),
                    fmt_metrica(soma_base_total),
                    fmt_metrica(soma_meta_total),
                    fmt_pct(crescimento_total),
                ]
            })

            df_export_detalhe = df_editado[
                ['Codigo', 'Nome', 'Base Historica', 'Crescimento %', 'Meta Final']
            ].copy()
            df_export_detalhe['Base Historica'] = df_export_detalhe['Base Historica'].apply(fmt_metrica)
            df_export_detalhe['Meta Final'] = df_export_detalhe['Meta Final'].apply(fmt_metrica)
            df_export_detalhe['Crescimento %'] = df_export_detalhe['Crescimento %'].apply(fmt_pct)

            buf_metas = io.BytesIO()
            with pd.ExcelWriter(buf_metas, engine='xlsxwriter') as w:
                df_export_resumo.to_excel(w, index=False, sheet_name='Resumo da Meta')
                df_export_detalhe.to_excel(w, index=False, sheet_name='Detalhamento')
                if not df_quebra_cliente.empty:
                    df_quebra_excel = df_quebra_cliente.copy()
                    df_quebra_excel['Base Historica Cliente'] = df_quebra_excel['Base Historica Cliente'].apply(fmt_metrica)
                    df_quebra_excel['Participacao na Rede %'] = df_quebra_excel['Participacao na Rede %'].apply(fmt_pct)
                    df_quebra_excel['Meta Cliente'] = df_quebra_excel['Meta Cliente'].apply(fmt_metrica)
                    df_quebra_excel.to_excel(w, index=False, sheet_name='Quebra por Cliente')
                
                df_hist_excel = pivot_hist_exib_top.copy()
                for c in cols_fmt_hist:
                    if c in df_hist_excel.columns:
                        df_hist_excel[c] = df_hist_excel[c].apply(fmt_metrica)
                df_hist_excel.to_excel(w, index=False, sheet_name='Historico de Referencia')

            st.download_button(
                "Exportar Meta para Excel",
                data=buf_metas.getvalue(),
                file_name="rotina_8020_meta_" + nivel_meta.replace(' ', '_').replace('/', '-') + ".xlsx",
                mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
            )
