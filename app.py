import streamlit as st
import pandas as pd
import numpy as np
import io
import datetime
import plotly.graph_objects as go
import plotly.express as px

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
MESES_LISTA_PADRAO = ['jan', 'fev', 'mar', 'abr', 'mai', 'jun', 'jul', 'ago', 'set', 'out', 'nov', 'dez']

# ==============================================================================
# 1. FUNÇÕES UTILITÁRIAS E FORMATADORES GLOBAL
# ==============================================================================
def processar_lista_input(texto):
    if not texto:
        return []
    return [l.strip() for l in texto.replace('\t', ' ').replace(',', ' ').split('\n') if l.strip()]

def delete_chave_cronologica(texto):
    try:
        m, a = str(texto).split('/')
        return (int(a), ORDER_MESES.get(m.lower(), 0))
    except Exception:
        return (99, 99)

def periodo_para_tupla(periodo_str):
    try:
        m, a = str(periodo_str).split('/')
        return (2000 + int(a), ORDER_MESES.get(m.lower(), 0))
    except Exception:
        return None

def tupla_para_periodo(ano, mes):
    return f"{NOME_MES_NUM.get(mes, '???')}/{str(ano)[-2:]}"

def somar_meses(ano, mes, n):
    total = (ano * 12 + (mes - 1)) + n
    novo_ano = total // 12
    novo_mes = total % 12 + 1
    return (novo_ano, novo_mes)

def fmt_brl(valor):
    try:
        if pd.isna(valor): return "R$ 0"
        return "R$ " + f"{int(round(valor)):,}".replace(',', '.')
    except Exception:
        return "R$ 0"

def fmt_inteiro(valor):
    try:
        if pd.isna(valor): return "0"
        return f"{int(round(valor)):,}".replace(',', '.')
    except Exception:
        return "0"

def fmt_pct(valor):
    try:
        return f"{valor:.2f}%".replace('.', ',') if not pd.isna(valor) else "0,00%"
    except Exception:
        return "0,00%"

def fmt_var(valor):
    try:
        if pd.isna(valor) or valor == float('inf') or valor == float('-inf'):
            return "-"
        if valor > 0:
            return f"\u25b2 +{valor:.2f}%".replace('.', ',')
        elif valor < 0:
            return f"\u25bc {valor:.2f}%".replace('.', ',')
        else:
            return "\u2796 0,00%"
    except Exception:
        return "-"

def fmt_var_pp(valor):
    try:
        if pd.isna(valor) or valor == float('inf') or valor == float('-inf'):
            return "-"
        if valor > 0:
            return f"\u25b2 +{valor:.2f} p.p.".replace('.', ',')
        elif valor < 0:
            return f"\u25bc {valor:.2f} p.p.".replace('.', ',')
        else:
            return "\u2796 0,00 p.p."
    except Exception:
        return "-"

def style_var_color(val):
    try:
        if isinstance(val, (int, float)):
            if val > 0: return 'color: #10b981; font-weight: bold;'
            if val < 0: return 'color: #ef4444; font-weight: bold;'
        if isinstance(val, str):
            if '\u25b2' in val or '+' in val: return 'color: #10b981; font-weight: bold;'
            if '\u25bc' in val or '-' in val: return 'color: #ef4444; font-weight: bold;'
    except Exception:
        pass
    return ''

def aplicar_cor_variacao(styler, colunas):
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

def definir_quadrante_absoluto(row):
    if row['TVENDA'] >= limite_faturamento and row['Margem_Global %'] >= limite_margem:
        return '⭐ Alta Contribuição'
    elif row['TVENDA'] >= limite_faturamento and row['Margem_Global %'] < limite_margem:
        return '📦 Volume Estratégico'
    elif row['TVENDA'] < limite_faturamento and row['Margem_Global %'] >= limite_margem:
        return '💎 Rentabilidade de Nicho'
    return '⚠️ Portfólio de Baixo Retorno'

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
            df[col] = pd.to_numeric(df[col], errors='coerce').fillna(0).astype('float64')
    return df

# ==============================================================================
# 2. CARREGAMENTO INICIAL DA BASE DE DADOS
# ==============================================================================
dados_originais = carregar_base()

# ==============================================================================
# 3. CONSTRUÇÃO COMPLETA DA SIDEBAR DE FILTROS
# ==============================================================================
st.sidebar.header("Filtros de Selecao")
anos_disponiveis = sorted(dados_originais['ANO_EIXO'].unique(), reverse=True)
ano_selecionado_ui = st.sidebar.selectbox("Ano de Análise", anos_disponiveis, index=0)
anos_selecionados = [ano_selecionado_ui]
ano_anterior_calc = str(int(ano_selecionado_ui) - 1)

df_temp = dados_originais[dados_originais['ANO_EIXO'].isin(anos_selecionados)]

meses_selecionados_raw = st.sidebar.multiselect("Meses Disponíveis", MESES_LISTA_PADRAO)
meses_alvo_limpos = meses_selecionados_raw if meses_selecionados_raw else MESES_LISTA_PADRAO
meses_selecionados = [f"{m}/{ano_selecionado_ui[-2:]}" for m in meses_alvo_limpos]

filiais_disponiveis = sorted(dados_originais['CODFILIAL'].unique())
filial_sel = st.sidebar.multiselect("Unidade / Filial", filiais_disponiveis)

redes_disponiveis = sorted(dados_originais['REDE'].dropna().unique())
rede_sel = st.sidebar.multiselect("Rede de Clientes", redes_disponiveis)

marcas_disponiveis = sorted(dados_originais['MARCA'].dropna().unique()) if 'MARCA' in dados_originais.columns else []
marca_sel = st.sidebar.multiselect("Marca do Produto", marcas_disponiveis)

st.sidebar.markdown("---")
st.sidebar.subheader("Réguas da Matriz de Portfólio")
limite_faturamento = st.sidebar.number_input("Corte - Faturamento Mínimo (R$)", min_value=0.0, value=1000000.0, step=50000.0, format="%.2f")
limite_margem = st.sidebar.number_input("Corte - Margem de Lucro Mínima (%)", min_value=-100.0, max_value=100.0, value=16.0, step=0.5, format="%.2f")

perfis_disponiveis = ["⭐ Alta Contribuição", "📦 Volume Estratégico", "💎 Rentabilidade de Nicho", "⚠️ Portfólio de Baixo Retorno"]
perfil_sel = st.sidebar.multiselect("Perfil Estratégico do Produto", perfis_disponiveis)

busca_cliente = st.sidebar.text_input("Buscar por Nome do Cliente")
busca_produto = st.sidebar.text_input("Buscar por Nome do Produto")

st.sidebar.markdown("---")
st.sidebar.header("Entrada de Listas (Excel)")
with st.sidebar.expander("Filtragem Avancada por Lotes"):
    input_codrede = st.text_area("Lista de Codigos de Rede")
    input_codcli  = st.text_area("Lista de Codigos de Cliente")
    input_codprod = st.text_area("Lista de Codigos de Produto")
    input_ean     = st.text_area("Lista de Codigos EAN")
    input_ncm     = st.text_area("Lista de Codigos NCM")

# ==============================================================================
# 4. PIPELINE DE FILTRAGEM COMERCIAL
# ==============================================================================
df_comercial_bruto = dados_originais.copy()
if filial_sel: df_comercial_bruto = df_comercial_bruto[df_comercial_bruto['CODFILIAL'].isin(filial_sel)]
if rede_sel: df_comercial_bruto = df_comercial_bruto[df_comercial_bruto['REDE'].isin(rede_sel)]
if marca_sel: df_comercial_bruto = df_comercial_bruto[df_comercial_bruto['MARCA'].isin(marca_sel)]
if busca_cliente: df_comercial_bruto = df_comercial_bruto[df_comercial_bruto['CLIENTE'].str.contains(busca_cliente, case=False, na=False)]
if busca_produto: df_comercial_bruto = df_comercial_bruto[df_comercial_bruto['DESCRICAO'].str.contains(busca_produto, case=False, na=False)]

for campo, lista in [
    ('CODREDE', processar_lista_input(input_codrede)), ('CODCLI', processar_lista_input(input_codcli)),
    ('CODPROD', processar_lista_input(input_codprod)), ('EAN', processar_lista_input(input_ean)), ('NCM', processar_lista_input(input_ncm)),
]:
    if lista and campo in df_comercial_bruto.columns:
        df_comercial_bruto = df_comercial_bruto[df_comercial_bruto[campo].astype(str).str.split('.').str[0].str.strip().isin(lista)]

# Consolidação do Quadrante por SKUs
df_recorte_temporal = df_comercial_bruto[df_comercial_bruto['ANO_EIXO'] == ano_selecionado_ui].copy()
df_global_prod = df_recorte_temporal.groupby('CODPROD').agg({'TVENDA': 'sum', 'TLUCRO': 'sum' if 'TLUCRO' in df_recorte_temporal.columns else 'count'}).reset_index()
df_global_prod['Margem_Global %'] = (df_global_prod['TLUCRO'] / df_global_prod['TVENDA'] * 100).where(df_global_prod['TVENDA'] > 0, 0) if 'TLUCRO' in df_recorte_temporal.columns else 0
df_global_prod['Quadrante_Fixo'] = df_global_prod.apply(definir_quadrante_absoluto, axis=1)
mapa_quadrantes = dict(zip(df_global_prod['CODPROD'], df_global_prod['Quadrante_Fixo']))

df_comercial_bruto['Quadrante_Fixo'] = df_comercial_bruto['CODPROD'].map(mapa_quadrantes).fillna('⚠️ Portfólio de Baixo Retorno')

# 🔥 SALVAMOS A BASE INTACTA ANTES DO FILTRO DO USUÁRIO
df_comercial_bruto_sem_perfil = df_comercial_bruto.copy()

# APLICA O FILTRO APENAS NA BASE OPERACIONAL (Usada nas outras abas)
if perfil_sel:
    df_comercial_bruto = df_comercial_bruto[df_comercial_bruto['Quadrante_Fixo'].isin(perfil_sel)]

# Filtros compartilhados pelas abas do painel
df_filtrado = df_comercial_bruto[df_comercial_bruto['ANO_EIXO'].isin([ano_selecionado_ui, ano_anterior_calc])].copy()
df_filtrado_metas = df_comercial_bruto.copy()

tab_clientes, tab_produtos, tab_inteligencia, tab_metas = st.tabs([
    "Clientes / Rede", "Produtos / Marca", "Inteligencia de Negocio", "Simulador de Metas"
])

# ==============================================================================
# 🎯 ABA 1 - CLIENTES / REDE
# ==============================================================================
with tab_clientes:
    df_ano_atual = df_comercial_bruto[
        (df_comercial_bruto['ANO_EIXO'] == ano_selecionado_ui) & 
        (df_comercial_bruto['PERIODO_LIMPO'].str.split('/').str[0].str.lower().isin(meses_alvo_limpos))
    ].copy()

    df_ano_anterior = df_comercial_bruto[
        (df_comercial_bruto['ANO_EIXO'] == ano_anterior_calc) & 
        (df_comercial_bruto['PERIODO_LIMPO'].str.split('/').str[0].str.lower().isin(meses_alvo_limpos))
    ].copy()

    if df_ano_atual.empty and df_ano_anterior.empty:
        st.warning("Sem dados comerciais no escopo selecionado.")
    else:
        op_visao = st.radio("Métrica de Análise Comercial", ["Faturamento (R$)", "Volume (Caixas)"], horizontal=True, key="op_vis_cli_new")
        col_analise = 'TVENDA' if op_visao == "Faturamento (R$)" else 'QT'
        fmt_visao = fmt_brl if op_visao == "Faturamento (R$)" else fmt_inteiro

        tot_atual_val = df_ano_atual[col_analise].sum()
        tot_ant_val = df_ano_anterior[col_analise].sum()
        delta_val = ((tot_atual_val - tot_ant_val) / tot_ant_val * 100) if tot_ant_val > 0 else 0

        tot_luc_atual = df_ano_atual['TLUCRO'].sum() if 'TLUCRO' in df_ano_atual.columns else 0
        tot_fat_atual = df_ano_atual['TVENDA'].sum()
        margem_atual = (tot_luc_atual / tot_fat_atual * 100) if tot_fat_atual > 0 else 0
        
        tot_luc_ant = df_ano_anterior['TLUCRO'].sum() if 'TLUCRO' in df_ano_anterior.columns else 0
        tot_fat_ant = df_ano_anterior['TVENDA'].sum()
        margem_ant = (tot_luc_ant / tot_fat_ant * 100) if tot_fat_ant > 0 else 0

        tot_pos_atual = df_ano_atual['CODCLI'].nunique()
        tot_pos_ant = df_ano_anterior['CODCLI'].nunique()
        delta_pos = ((tot_pos_atual - tot_pos_ant) / tot_pos_ant * 100) if tot_pos_ant > 0 else 0

        st.write("### Indicadores YoY Gerenciais")
        k1, k2, k3, k4, k5 = st.columns(5)
        k1.metric(f"{op_visao.split(' ')[0]} {ano_selecionado_ui}", fmt_visao(tot_atual_val), delta=f"{delta_val:+.2f}% vs {ano_anterior_calc}")
        k2.metric(f"{op_visao.split(' ')[0]} {ano_anterior_calc}", fmt_visao(tot_ant_val))
        k3.metric(f"Positivação {ano_selecionado_ui}", f"{tot_pos_atual:,}".replace(',', '.'), delta=f"{delta_pos:+.2f}% vs {ano_anterior_calc}")
        k4.metric(f"Positivação {ano_anterior_calc}", f"{tot_pos_ant:,}".replace(',', '.'))
        k5.metric(f"Margem {ano_selecionado_ui}", fmt_pct(margem_atual), delta=fmt_var_pp(margem_atual - margem_ant))

        st.markdown("---")

        linhas_resumo_mensal = []
        for m_lbl in meses_alvo_limpos:
            val_ant_m = df_ano_anterior[df_ano_anterior['PERIODO_LIMPO'].str.lower().str.startswith(m_lbl)][col_analise].sum()
            val_atual_m = df_ano_atual[df_ano_atual['PERIODO_LIMPO'].str.lower().str.startswith(m_lbl)][col_analise].sum()
            evo_val_m = ((val_atual_m - val_ant_m) / val_ant_m * 100) if val_ant_m > 0 else 0
            
            pos_ant_m = df_ano_anterior[df_ano_anterior['PERIODO_LIMPO'].str.lower().str.startswith(m_lbl)]['CODCLI'].nunique()
            pos_atual_m = df_ano_atual[df_ano_atual['PERIODO_LIMPO'].str.lower().str.startswith(m_lbl)]['CODCLI'].nunique()
            evo_pos_m = ((pos_atual_m - pos_ant_m) / pos_ant_m * 100) if pos_ant_m > 0 else 0
            
            linhas_resumo_mensal.append({
                'Mês': m_lbl.upper(), f'{ano_anterior_calc} ': val_ant_m, f'{ano_selecionado_ui} ': val_atual_m,
                'Evolução %': evo_val_m, f'Posit. {ano_anterior_calc}': pos_ant_m, f'Posit. {ano_selecionado_ui}': pos_atual_m,
                'Evolução Posit. %': evo_pos_m
            })
            
        df_resumo_mensal = pd.DataFrame(linhas_resumo_mensal)
        
        config_colunas_resumo = {
            'Evolução %': st.column_config.NumberColumn('Evolução %', format="%.2f%%"),
            'Evolução Posit. %': st.column_config.NumberColumn('Evolução Posit. %', format="%.2f%%"),
            f'{ano_anterior_calc} ': st.column_config.NumberColumn(f'{ano_anterior_calc} ', format="R$ %,.0f" if col_analise=='TVENDA' else "%,.0f"),
            f'{ano_selecionado_ui} ': st.column_config.NumberColumn(f'{ano_selecionado_ui} ', format="R$ %,.0f" if col_analise=='TVENDA' else "%,.0f"),
            f'Posit. {ano_anterior_calc}': st.column_config.NumberColumn(f'Posit. {ano_anterior_calc}', format="%,.0f"),
            f'Posit. {ano_selecionado_ui}': st.column_config.NumberColumn(f'Posit. {ano_selecionado_ui}', format="%,.0f"),
        }
        
        st.dataframe(
            df_resumo_mensal.style.pipe(aplicar_cor_variacao, ['Evolução %', 'Evolução Posit. %']),
            use_container_width=True, hide_index=True, column_config=config_colunas_resumo
        )

        st.markdown("---")

        def construir_grade_yoy(df_escopo_atual, df_escopo_anterior, index_cols, col_nome_tot_atual):
            piv_ant = df_escopo_anterior.pivot_table(index=index_cols, columns='PERIODO_LIMPO', values=col_analise, aggfunc='sum').fillna(0)
            piv_atual = df_escopo_atual.pivot_table(index=index_cols, columns='PERIODO_LIMPO', values=col_analise, aggfunc='sum').fillna(0)
            
            colunas_completas = []
            config_grade = {}
            
            for m_lbl in meses_alvo_limpos:
                c_ant = f"{m_lbl}/{ano_anterior_calc[-2:]}"
                c_atual = f"{m_lbl}/{ano_selecionado_ui[-2:]}"
                c_var = f"Var. {m_lbl.upper()} %"
                if c_ant not in piv_ant.columns: piv_ant[c_ant] = 0.0
                if c_atual not in piv_atual.columns: piv_atual[c_atual] = 0.0
                colunas_completas += [c_ant, c_atual, c_var]
                
                config_grade[c_ant] = st.column_config.NumberColumn(c_ant, format="R$ %,.0f" if col_analise=='TVENDA' else "%,.0f")
                config_grade[c_atual] = st.column_config.NumberColumn(c_atual, format="R$ %,.0f" if col_analise=='TVENDA' else "%,.0f")
                config_grade[c_var] = st.column_config.NumberColumn(c_var, format="%.2f%%")

            df_join = piv_ant.join(piv_atual, how='outer', lsuffix='_ant', rsuffix='_atual').fillna(0)
            
            for m_lbl in meses_alvo_limpos:
                c_ant = f"{m_lbl}/{ano_anterior_calc[-2:]}"
                c_atual = f"{m_lbl}/{ano_selecionado_ui[-2:]}"
                c_var = f"Var. {m_lbl.upper()} %"
                df_join[c_var] = ((df_join[c_atual] - df_join[c_ant]) / df_join[c_ant].replace(0, np.nan)) * 100

            df_join[f'Acumulado {ano_anterior_calc}'] = df_escopo_anterior.groupby(index_cols)[col_analise].sum().reindex(df_join.index).fillna(0)
            df_join[col_nome_tot_atual] = df_escopo_atual.groupby(index_cols)[col_analise].sum().reindex(df_join.index).fillna(0)
            df_join['Evolução Total %'] = ((df_join[col_nome_tot_atual] - df_join[f'Acumulado {ano_anterior_calc}']) / df_join[f'Acumulado {ano_anterior_calc}'].replace(0, np.nan)) * 100
            
            df_join = df_join.sort_values(col_nome_tot_atual, ascending=False)
            df_join['Acum_ABC'] = df_join[col_nome_tot_atual].cumsum()
            soma_abc_tot = df_join[col_nome_tot_atual].sum()
            df_join['Pct_ABC'] = (df_join['Acum_ABC'] / soma_abc_tot * 100) if soma_abc_tot > 0 else 0
            df_join['Curva ABC'] = df_join['Pct_ABC'].apply(lambda x: 'A' if x <= 80 else ('B' if x <= 95 else 'C'))
            
            config_grade[f'Acumulado {ano_anterior_calc}'] = st.column_config.NumberColumn(f'Acumulado {ano_anterior_calc}', format="R$ %,.0f" if col_analise=='TVENDA' else "%,.0f")
            config_grade[col_nome_tot_atual] = st.column_config.NumberColumn(col_nome_tot_atual, format="R$ %,.0f" if col_analise=='TVENDA' else "%,.0f")
            config_grade['Evolução Total %'] = st.column_config.NumberColumn('Evolução Total %', format="%.2f%%")

            return df_join.reset_index(), colunas_completas, config_grade

        st.write("### 🏢 Resultados por Rede (YoY)")
        df_rede_yoy, col_meses_rede, config_rede = construir_grade_yoy(df_ano_atual, df_ano_anterior, ['CODREDE', 'REDE'], f'Acumulado {ano_selecionado_ui}')
        cols_exib_rede = ['Curva ABC', 'CODREDE', 'REDE'] + col_meses_rede + [f'Acumulado {ano_anterior_calc}', f'Acumulado {ano_selecionado_ui}', 'Evolução Total %']
        cols_var_rede = [c for c in cols_exib_rede if 'Var.' in c or 'Evolução' in c]
        st.dataframe(df_rede_yoy[cols_exib_rede].style.pipe(aplicar_cor_variacao, cols_var_rede), use_container_width=True, height=350, hide_index=True, column_config=config_rede)

        st.markdown("---")

        st.write("### 👥 Resultados por Cliente e Rede (YoY)")
        df_cli_yoy, col_meses_cli, config_cli = construir_grade_yoy(df_ano_atual, df_ano_anterior, ['CODREDE', 'REDE', 'CODCLI', 'CLIENTE'], f'Acumulado {ano_selecionado_ui}')
        cols_exib_cli = ['Curva ABC', 'CODREDE', 'REDE', 'CODCLI', 'CLIENTE'] + col_meses_cli + [f'Acumulado {ano_anterior_calc}', f'Acumulado {ano_selecionado_ui}', 'Evolução Total %']
        cols_var_cli = [c for c in cols_exib_cli if 'Var.' in c or 'Evolução' in c]
        st.dataframe(df_cli_yoy[cols_exib_cli].style.pipe(aplicar_cor_variacao, cols_var_cli), use_container_width=True, height=450, hide_index=True, column_config=config_cli)

        st.markdown("---")

        st.write("### 📊 Inteligência Visual de Crescimento")
        c_graph1, c_graph2 = st.columns(2)
        
        with c_graph1:
            st.write(f"**Visual 1: Confrontação de Performance Mensal ({op_visao.split(' ')[0]})**")
            fig_bar_yoy = go.Figure()
            text_ant_hover = [fmt_visao(v) for v in df_resumo_mensal[f'{ano_anterior_calc} '].values]
            text_atual_hover = [fmt_visao(v) for v in df_resumo_mensal[f'{ano_selecionado_ui} '].values]

            fig_bar_yoy.add_trace(go.Bar(
                x=df_resumo_mensal['Mês'], y=df_resumo_mensal[f'{ano_anterior_calc} '],
                name=ano_anterior_calc, marker_color='#475569', customdata=text_ant_hover,
                hovertemplate='Mês: %{x}<br>Volume: %{customdata}<extra></extra>'
            ))
            fig_bar_yoy.add_trace(go.Bar(
                x=df_resumo_mensal['Mês'], y=df_resumo_mensal[f'{ano_selecionado_ui} '],
                name=ano_selecionado_ui, marker_color='#3b82f6', customdata=text_atual_hover,
                hovertemplate='Mês: %{x}<br>Volume: %{customdata}<extra></extra>'
            ))
            layout_bar_yoy = base_layout(380)
            layout_bar_yoy['barmode'] = 'group'
            fig_bar_yoy.update_layout(**layout_bar_yoy)
            st.plotly_chart(fig_bar_yoy, use_container_width=True)
            
        with c_graph2:
            st.write(f"**Visual 2: Matriz de Tração e Dispersão de Crescimento de Redes**")
            df_scatter_base = df_rede_yoy[df_rede_yoy[f'Acumulado {ano_selecionado_ui}'] > 0].copy()
            
            hover_scat_text = []
            for _, row in df_scatter_base.iterrows():
                txt = (
                    f"<b>{row['REDE']}</b><br>"
                    f"Volume Atual: {fmt_visao(row[f'Acumulado {ano_selecionado_ui}'])}<br>"
                    f"Crescimento YoY: {row['Evolução Total %']:.2f}%".replace('.', ',')
                )
                hover_scat_text.append(txt)
            df_scatter_base['hover_text'] = hover_scat_text

            fig_scatter_yoy = px.scatter(
                df_scatter_base, x=f'Acumulado {ano_selecionado_ui}', y='Evolução Total %',
                size=f'Acumulado {ano_selecionado_ui}', color_discrete_sequence=['#3b82f6'],
                custom_data=['hover_text']
            )
            fig_scatter_yoy.update_traces(hovertemplate="%{customdata[0]}<extra></extra>")
            fig_scatter_yoy.add_hline(y=0.0, line_dash="dash", line_color="#ef4444", line_width=1.5)
            
            layout_scat = base_layout(380)
            layout_scat['plot_bgcolor'] = 'rgba(156, 163, 175, 0.05)'
            fig_scatter_yoy.update_layout(**layout_scat)
            fig_scatter_yoy.update_yaxes(ticksuffix="%")
            st.plotly_chart(fig_scatter_yoy, use_container_width=True)

        buf_cli = io.BytesIO()
        with pd.ExcelWriter(buf_cli, engine='xlsxwriter') as w:
            df_res_excel = df_resumo_mensal.copy()
            df_res_excel['Evolução %'] = df_res_excel['Evolução %'].apply(fmt_var)
            df_res_excel['Evolução Posit. %'] = df_res_excel['Evolução Posit. %'].apply(fmt_var)
            df_res_excel.to_excel(w, index=False, sheet_name='Resumo_Mensal_YoY')
            
            df_rede_excel = df_rede_yoy[cols_exib_rede].copy()
            for c in cols_var_rede: df_rede_excel[c] = df_rede_excel[c].apply(fmt_var)
            df_rede_excel.to_excel(w, index=False, sheet_name='Grade_Redes_YoY')
            
            df_cli_excel = df_cli_yoy[cols_exib_cli].copy()
            for c in cols_var_cli: df_cli_excel[c] = df_cli_excel[c].apply(fmt_var)
            df_cli_excel.to_excel(w, index=False, sheet_name='Grade_Clientes_YoY')

        st.download_button(
            "Exportar Rotina YoY para Excel", data=buf_cli.getvalue(),
            file_name=f"rotina_yoy_clientes_{ano_selecionado_ui}.xlsx", mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
        )

# ==============================================================================
# 🎯 ABA 2 - PRODUTOS / MARCA
# ==============================================================================
with tab_produtos:
    # Bases: Uma intacta (para Marcas) e uma já com os cortes de SKU (para Produtos)
    df_produtos_escopo_full = df_comercial_bruto_sem_perfil[df_comercial_bruto_sem_perfil['ANO_EIXO'].isin([ano_selecionado_ui, ano_anterior_calc])].copy()
    df_produtos_escopo = df_comercial_bruto[df_comercial_bruto['ANO_EIXO'].isin([ano_selecionado_ui, ano_anterior_calc])].copy()

    if df_produtos_escopo_full.empty:
        st.warning("Sem dados para os filtros aplicados.")
    else:
        op_visao_prod = st.radio("Metrica de Visualizacao Comercial (Aba Produtos)", ["Faturamento (R$)", "Volume (Caixas)"], horizontal=True, key="op_visao_prod")
        col_analise_prod = 'TVENDA' if op_visao_prod == "Faturamento (R$)" else 'QT'
        fmt_visao_prod = fmt_brl if op_visao_prod == "Faturamento (R$)" else fmt_inteiro

        visao_matriz = st.radio("Visão da Matriz e Tabela", ["Marca", "Produto"], index=0, horizontal=True, key="visao_matriz_prod")

        if visao_matriz == "Marca" and 'MARCA' in df_produtos_escopo_full.columns:
            # 1. Limpeza padronizada da marca para evitar duplicidade oculta
            df_produtos_escopo_full['MARCA'] = df_produtos_escopo_full['MARCA'].astype(str).str.strip().str.upper()
            
            agg_matriz = {'QT': 'sum', 'TVENDA': 'sum'}
            if 'TLUCRO' in df_produtos_escopo_full.columns: agg_matriz['TLUCRO'] = 'sum'
            col_cliente_detectada = [c for c in ['CODCLI', 'CLIENTE', 'CLIENTE_CHAVE'] if c in df_produtos_escopo_full.columns]
            if col_cliente_detectada: agg_matriz[col_cliente_detectada[0]] = 'nunique'
            
            # 2. Agraga a marca INTACTA para descobrir a margem VERDADEIRA da marca no período
            df_plot_base = df_produtos_escopo_full.groupby(['MARCA']).agg(agg_matriz).reset_index()
            df_plot_base['Margem %'] = (df_plot_base['TLUCRO'] / df_plot_base['TVENDA'] * 100).where(df_plot_base['TVENDA'] > 0, 0) if 'TLUCRO' in df_plot_base.columns else 0
            
            # 3. Classifica a Marca
            df_plot_base['Margem_Global %'] = df_plot_base['Margem %']
            df_plot_base['Quadrante_Fixo'] = df_plot_base.apply(definir_quadrante_absoluto, axis=1)
            
            # 4. AGORA sim aplicamos o seu filtro lateral como um "Filtro de Exibição"
            if perfil_sel:
                df_plot_base = df_plot_base[df_plot_base['Quadrante_Fixo'].isin(perfil_sel)]
            
            df_plot_base = df_plot_base.sort_values('TVENDA', ascending=False)
            df_plot_base['Acumulado'] = df_plot_base['TVENDA'].cumsum()
            soma_fat_plot = df_plot_base['TVENDA'].sum()
            df_plot_base['Pct Acumulado'] = (df_plot_base['Acumulado'] / soma_fat_plot * 100) if soma_fat_plot > 0 else 0
            df_plot_base['Curva ABC'] = df_plot_base['Pct Acumulado'].apply(lambda x: 'A' if x <= 80 else ('B' if x <= 95 else 'C'))

            # Setup dos KPIs Superiores
            total_itens = df_plot_base['MARCA'].nunique()
            itens_curva_a = df_plot_base[df_plot_base['Curva ABC'] == 'A']['MARCA'].nunique()
            pct_itens_a = (itens_curva_a / total_itens * 100) if total_itens > 0 else 0
            fat_quad = df_plot_base['TVENDA'].sum()
            lucro_quad = df_plot_base['TLUCRO'].sum() if 'TLUCRO' in df_plot_base.columns else 0
            lbl_kpi1, lbl_kpi2 = "Total de Marcas Exibidas", "Marcas na Curva A"

            # Prepara a base dos visuais abaixo para refletir apenas as marcas validadas neste filtro
            marcas_validas = df_plot_base['MARCA'].unique().tolist()
            df_visuals_base = df_produtos_escopo_full[df_produtos_escopo_full['MARCA'].isin(marcas_validas)].copy()

        else:
            # Visão Padrão: Produto (Pode usar a base com os cortes originais sem problemas)
            agg_cols = {'QT': 'sum', 'TVENDA': 'sum'}
            grp_cols = ['CODPROD', 'DESCRICAO', 'Quadrante_Fixo']
            if 'MARCA' in df_produtos_escopo.columns: grp_cols.append('MARCA')
            if 'NCM' in df_produtos_escopo.columns: grp_cols.append('NCM')
            if 'TLUCRO' in df_produtos_escopo.columns: agg_cols['TLUCRO'] = 'sum'
            col_cliente_detectada = [c for c in ['CODCLI', 'CLIENTE', 'CLIENTE_CHAVE'] if c in df_produtos_escopo.columns]
            if col_cliente_detectada: agg_cols[col_cliente_detectada[0]] = 'nunique'

            df_plot_base = df_produtos_escopo.groupby(grp_cols).agg(agg_cols).reset_index()
            df_plot_base['Margem %'] = (df_plot_base['TLUCRO'] / df_plot_base['TVENDA'] * 100).where(df_plot_base['TVENDA'] > 0, 0) if 'TLUCRO' in df_plot_base.columns else 0

            df_plot_base = df_plot_base.sort_values('TVENDA', ascending=False)
            df_plot_base['Acumulado'] = df_plot_base['TVENDA'].cumsum()
            soma_fat_plot = df_plot_base['TVENDA'].sum()
            df_plot_base['Pct Acumulado'] = (df_plot_base['Acumulado'] / soma_fat_plot * 100) if soma_fat_plot > 0 else 0
            df_plot_base['Curva ABC'] = df_plot_base['Pct Acumulado'].apply(lambda x: 'A' if x <= 80 else ('B' if x <= 95 else 'C'))

            total_itens = df_plot_base['CODPROD'].nunique()
            itens_curva_a = df_plot_base[df_plot_base['Curva ABC'] == 'A']['CODPROD'].nunique()
            pct_itens_a = (itens_curva_a / total_itens * 100) if total_itens > 0 else 0
            fat_quad = df_plot_base['TVENDA'].sum()
            lucro_quad = df_plot_base['TLUCRO'].sum() if 'TLUCRO' in df_plot_base.columns else 0
            lbl_kpi1, lbl_kpi2 = "Total de SKUs Exibidos", "SKUs na Curva A"

            df_visuals_base = df_produtos_escopo.copy()
            if 'MARCA' in df_visuals_base.columns:
                df_visuals_base['MARCA'] = df_visuals_base['MARCA'].astype(str).str.strip().str.upper()

        # --- EXIBIÇÃO DOS KPIS ---
        c_p_k1, c_p_k2, c_p_k3, c_p_k4 = st.columns(4)
        with c_p_k1: st.metric(lbl_kpi1, f"{total_itens}")
        with c_p_k2: st.metric(lbl_kpi2, f"{itens_curva_a} ({pct_itens_a:.1f}%)")
        with c_p_k3: st.metric("Faturamento do Bloco", fmt_brl(fat_quad))
        with c_p_k4:
            if fat_quad > 0: st.metric("Margem Média do Bloco", f"{(lucro_quad / fat_quad) * 100:.2f}%")
            else: st.metric("Margem Média do Bloco", "N/A")

        st.markdown("---")

        # --- MATRIZ SCATTER ---
        if 'TLUCRO' in df_produtos_escopo_full.columns and not df_plot_base.empty:
            st.write("### 🎯 Matriz de Posicionamento de Portfólio (Margem vs. Faturamento)")
            
            hover_text = []
            for idx, row in df_plot_base.iterrows():
                cli_str = f"<br>Clientes Posit.: {int(row[col_cliente_detectada[0]])}" if col_cliente_detectada else ""
                lucro_str = f"<br>Lucro Bruto: R$ {row['TLUCRO']:,.2f}".replace(',', 'X').replace('.', ',').replace('X', '.') if 'TLUCRO' in row else ""
                vol_str = f"<br>Volume: {int(row['QT']):,}".replace(',', '.')
                
                if visao_matriz == "Marca":
                    header_txt = f"<b>{row['MARCA']}</b><br>"
                else:
                    header_txt = f"<b>{row['DESCRICAO']}</b> (Cód: {row['CODPROD']})<br>"

                txt = (
                    header_txt +
                    f"Classificação: {row['Quadrante_Fixo']}<br>"
                    f"Faturamento: R$ {row['TVENDA']:,.2f}<br>".replace(',', 'X').replace('.', ',').replace('X', '.') +
                    f"Margem: {row['Margem %']:.2f}%" + lucro_str + vol_str + cli_str
                )
                hover_text.append(txt)
            df_plot_base['hover_text'] = hover_text
            
            fig_quadrantes = px.scatter(
                df_plot_base, x='TVENDA', y='Margem %', color='Quadrante_Fixo', size='QT', size_max=50,
                color_discrete_map={
                    '⭐ Alta Contribuição': '#38BDF8', '📦 Volume Estratégico': '#3B82F6',     
                    '💎 Rentabilidade de Nicho': '#34D399', '⚠️ Portfólio de Baixo Retorno': '#F87171' 
                },
                labels={'TVENDA': 'Faturamento (R$)', 'Margem %': 'Margem de Lucro (%)'},
                custom_data=['hover_text'] # Trava a injeção do texto exatamente na bolha lida
            )
            fig_quadrantes.update_traces(hovertemplate="%{customdata[0]}<extra></extra>")
            fig_quadrantes.add_vline(x=limite_faturamento, line_dash="dash", line_color="#9CA3AF", line_width=1.5, annotation_text="Corte Faturamento", annotation_position="top left", annotation_font_color="#9CA3AF")
            fig_quadrantes.add_hline(y=limite_margem, line_dash="dash", line_color="#9CA3AF", line_width=1.5, annotation_text="Corte Margem", annotation_position="bottom right", annotation_font_color="#9CA3AF")
            
            fig_quadrantes.update_layout(plot_bgcolor='rgba(0,0,0,0)', paper_bgcolor='rgba(0,0,0,0)', height=520, legend=dict(orientation="h", yanchor="bottom", y=1.05, xanchor="center", x=0.5, title_text="", font=dict(color="#9CA3AF")), margin=dict(l=40, r=40, t=50, b=40))
            fig_quadrantes.update_xaxes(showgrid=True, gridcolor='rgba(156, 163, 175, 0.15)', tickfont=dict(color="#9CA3AF"), title_font=dict(color="#9CA3AF"))
            fig_quadrantes.update_yaxes(showgrid=True, gridcolor='rgba(156, 163, 175, 0.15)', ticksuffix="%", tickfont=dict(color="#9CA3AF"), title_font=dict(color="#9CA3AF"))
            st.plotly_chart(fig_quadrantes, use_container_width=True)

        st.markdown("---")

        # --- TABELA DETALHADA ---
        if visao_matriz == "Marca":
            st.write("### Detalhamento Comercial e Gerencial de Marcas")
        else:
            st.write("### Detalhamento Comercial e Gerencial de SKUs")
            
        rename_map = {'CODPROD': 'Codigo', 'DESCRICAO': 'Produto', 'MARCA': 'Marca', 'QT': 'Vol. Caixas', 'TVENDA': 'Faturamento', 'TLUCRO': 'Lucro Bruto', 'Quadrante_Fixo': 'Perfil Estratégico'}
        if col_cliente_detectada: rename_map[col_cliente_detectada[0]] = 'Clientes Posit.'
        df_prod_tabela = df_plot_base.rename(columns={k: v for k, v in rename_map.items() if k in df_plot_base.columns})
        
        base_cols = ['Curva ABC', 'Perfil Estratégico']
        
        if visao_matriz == "Marca":
            if 'Marca' in df_prod_tabela.columns: base_cols.append('Marca')
        else:
            base_cols.extend(['Codigo', 'Produto'])
            if 'Marca' in df_prod_tabela.columns: base_cols.append('Marca')
            if 'NCM' in df_prod_tabela.columns: base_cols.append('NCM')
            
        base_cols += ['Vol. Caixas', 'Faturamento']
        if 'Clientes Posit.' in df_prod_tabela.columns: base_cols.append('Clientes Posit.')
        if 'Lucro Bruto' in df_prod_tabela.columns: base_cols.append('Lucro Bruto')
        if 'Margem %' in df_prod_tabela.columns: base_cols.append('Margem %')

        fmt_prod = {'Vol. Caixas': lambda x: f"{int(x):,}".replace(',', '.'), 'Faturamento': fmt_brl}
        if 'Clientes Posit.' in df_prod_tabela.columns: fmt_prod['Clientes Posit.'] = lambda x: f"{int(x)}"
        if 'Lucro Bruto' in df_prod_tabela.columns: fmt_prod['Lucro Bruto'] = fmt_brl
        if 'Margem %' in df_prod_tabela.columns: fmt_prod['Margem %'] = fmt_pct
        st.dataframe(df_prod_tabela[base_cols].style.format(fmt_prod), use_container_width=True, height=380, hide_index=True)

        st.markdown("---")

        # --- EFICIÊNCIA LOGÍSTICA ---
        st.write("### 🚚 Eficiência Logística: Lucro Real por Caixa vs. Densidade de Giro")
        df_log_excel_export = pd.DataFrame()

        if 'TLUCRO' in df_plot_base.columns and not df_plot_base.empty:
            df_logistica = df_plot_base.copy()
            df_logistica['Lucro por Caixa'] = df_logistica['TLUCRO'] / df_logistica['QT'].replace(0, np.nan)
            df_logistica['Faturamento por Caixa'] = df_logistica['TVENDA'] / df_logistica['QT'].replace(0, np.nan)
            df_logistica = df_logistica.sort_values('QT', ascending=False).reset_index(drop=True)

            col_log1, col_log2 = st.columns([1, 1])
            with col_log1:
                if visao_matriz == 'Marca':
                    df_log_tabela = df_logistica.rename(columns={'MARCA': 'Nome', 'QT': 'Vol. Caixas', 'TVENDA': 'Faturamento Total', 'TLUCRO': 'Lucro Total', 'Faturamento por Caixa': 'Fat. / Caixa', 'Lucro por Caixa': 'Lucro / Caixa'})
                    cols_log_exib = ['Nome', 'Vol. Caixas', 'Faturamento Total', 'Lucro Total', 'Fat. / Caixa', 'Lucro / Caixa']
                else:
                    df_log_tabela = df_logistica.rename(columns={'CODPROD': 'Código', 'DESCRICAO': 'Nome', 'QT': 'Vol. Caixas', 'TVENDA': 'Faturamento Total', 'TLUCRO': 'Lucro Total', 'Faturamento por Caixa': 'Fat. / Caixa', 'Lucro por Caixa': 'Lucro / Caixa'})
                    cols_log_exib = ['Código', 'Nome', 'Vol. Caixas', 'Faturamento Total', 'Lucro Total', 'Fat. / Caixa', 'Lucro / Caixa']

                fmt_log = {'Vol. Caixas': lambda x: f"{int(x):,}".replace(',', '.'), 'Faturamento Total': fmt_brl, 'Lucro Total': fmt_brl, 'Fat. / Caixa': lambda x: f"R$ {x:.2f}".replace('.', ','), 'Lucro / Caixa': lambda x: f"R$ {x:.2f}".replace('.', ',')}
                st.dataframe(df_log_tabela[cols_log_exib].style.format(fmt_log), use_container_width=True, hide_index=True, height=380)
                df_log_excel_export = df_log_tabela[cols_log_exib].copy()
            
            with col_log2:
                df_log_plot = df_log_tabela.head(10).sort_values('Lucro / Caixa', ascending=True)
                fig_log = go.Figure()
                fig_log.add_trace(go.Bar(y=df_log_plot['Nome'], x=df_log_plot['Lucro / Caixa'], orientation='h', marker_color='#10B981', hovertemplate='<b>%{y}</b><br>Lucro Real por Caixa: R$ %{x:,.2f}<extra></extra>'))
                layout_log = base_layout(380)
                layout_log['xaxis'] = dict(gridcolor=PLOT_GRID, tickprefix='R$ ')
                fig_log.update_layout(**layout_log)
                st.plotly_chart(fig_log, use_container_width=True)

        st.markdown("---")

        # --- HEATMAP E GRADE YOY MARCAS ---
        if 'MARCA' in df_visuals_base.columns:
            st.write(f"### Participacao de {op_visao_prod.split(' ')[0]} por Marca (Top 10)")
            colunas_meses_prod = sorted(df_visuals_base['PERIODO_LIMPO'].unique(), key=delete_chave_cronologica)
            top10_marcas = df_visuals_base.groupby('MARCA')[col_analise_prod].sum().sort_values(ascending=False).head(10).index.tolist()
            df_evo_marca_hm = df_visuals_base[df_visuals_base['MARCA'].isin(top10_marcas)].pivot_table(index='MARCA', columns='PERIODO_LIMPO', values=col_analise_prod, aggfunc='sum').reindex(columns=colunas_meses_prod, fill_value=0)
            df_evo_marca_hm['Total'] = df_evo_marca_hm.sum(axis=1)
            df_evo_hm_plot = df_evo_marca_hm.sort_values('Total', ascending=True).drop(columns=['Total'])

            z_data = df_evo_hm_plot.values
            text_data = [[abrev_brl(val) if col_analise_prod == 'TVENDA' else f"{val/1000:.1f}K".replace('.', ',') if val >= 1000 else f"{val:.0f}" for val in row] for row in z_data]
            fig_hm = go.Figure(data=go.Heatmap(z=z_data, x=colunas_meses_prod, y=df_evo_hm_plot.index, text=text_data, texttemplate="%{text}", colorscale='Blues', showscale=False, hovertemplate='<b>%{y}</b><br>%{x}<br>' + ('R$ %{z:,.2f}' if col_analise_prod == 'TVENDA' else '%{z:,.0f} Caixas') + '<extra></extra>'))
            layout_hm = base_layout(450)
            fig_hm.update_layout(**layout_hm)
            st.plotly_chart(fig_hm, use_container_width=True)

            st.markdown("---")

            st.write("### 🏷️ Grade Completa de Desempenho por Marca (YoY Lado a Lado)")
            
            df_marca_atual = df_visuals_base[
                (df_visuals_base['ANO_EIXO'] == ano_selecionado_ui) & 
                (df_visuals_base['PERIODO_LIMPO'].str.split('/').str[0].str.lower().isin(meses_alvo_limpos))
            ].copy()
            df_marca_anterior = df_visuals_base[
                (df_visuals_base['ANO_EIXO'] == ano_anterior_calc) & 
                (df_visuals_base['PERIODO_LIMPO'].str.split('/').str[0].str.lower().isin(meses_alvo_limpos))
            ].copy()

            piv_m_ant = df_marca_anterior.pivot_table(index=['MARCA'], columns='PERIODO_LIMPO', values=col_analise_prod, aggfunc='sum').fillna(0)
            piv_m_atual = df_marca_atual.pivot_table(index=['MARCA'], columns='PERIODO_LIMPO', values=col_analise_prod, aggfunc='sum').fillna(0)
            
            col_meses_marca = []
            fmt_map_marca_st = {}
            
            for m_lbl in meses_alvo_limpos:
                c_ant = f"{m_lbl}/{ano_anterior_calc[-2:]}"
                c_atual = f"{m_lbl}/{ano_selecionado_ui[-2:]}"
                c_var = f"Var. {m_lbl.upper()} %"
                if c_ant not in piv_m_ant.columns: piv_m_ant[c_ant] = 0.0
                if c_atual not in piv_m_atual.columns: piv_m_atual[c_atual] = 0.0
                col_meses_marca += [c_ant, c_atual, c_var]
                
                fmt_map_marca_st[c_ant] = fmt_visao_prod
                fmt_map_marca_st[c_atual] = fmt_visao_prod
                fmt_map_marca_st[c_var] = fmt_var

            df_marca_join = piv_m_ant.join(piv_m_atual, how='outer', lsuffix='_ant', rsuffix='_atual').fillna(0)
            
            for m_lbl in meses_alvo_limpos:
                c_ant = f"{m_lbl}/{ano_anterior_calc[-2:]}"
                c_atual = f"{m_lbl}/{ano_selecionado_ui[-2:]}"
                c_var = f"Var. {m_lbl.upper()} %"
                df_marca_join[c_var] = ((df_marca_join[c_atual] - df_marca_join[c_ant]) / df_marca_join[c_ant].replace(0, np.nan)) * 100

            df_marca_join[f'Acumulado {ano_anterior_calc}'] = df_marca_anterior.groupby(['MARCA'])[col_analise_prod].sum().reindex(df_marca_join.index).fillna(0)
            df_marca_join[f'Acumulado {ano_selecionado_ui}'] = df_marca_atual.groupby(['MARCA'])[col_analise_prod].sum().reindex(df_marca_join.index).fillna(0)
            df_marca_join['Evolução Total %'] = ((df_marca_join[f'Acumulado {ano_selecionado_ui}'] - df_marca_join[f'Acumulado {ano_anterior_calc}']) / df_marca_join[f'Acumulado {ano_anterior_calc}'].replace(0, np.nan)) * 100
            
            df_marca_join = df_marca_join.sort_values(f'Acumulado {ano_selecionado_ui}', ascending=False)
            df_marca_join['Acum_ABC'] = df_marca_join[f'Acumulado {ano_selecionado_ui}'].cumsum()
            soma_abc_m = df_marca_join[f'Acumulado {ano_selecionado_ui}'].sum()
            df_marca_join['Pct_ABC'] = (df_marca_join['Acum_ABC'] / soma_abc_m * 100) if soma_abc_m > 0 else 0
            df_marca_join['Curva ABC'] = df_marca_join['Pct_ABC'].apply(lambda x: 'A' if x <= 80 else ('B' if x <= 95 else 'C'))
            df_marca_join = df_marca_join.reset_index()

            cols_exib_marca = ['Curva ABC', 'MARCA'] + col_meses_marca + [f'Acumulado {ano_anterior_calc}', f'Acumulado {ano_selecionado_ui}', 'Evolução Total %']
            cols_var_marca = [c for c in cols_exib_marca if 'Var.' in c or 'Evolução' in c]
            
            fmt_map_marca_st[f'Acumulado {ano_anterior_calc}'] = fmt_visao_prod
            fmt_map_marca_st[f'Acumulado {ano_selecionado_ui}'] = fmt_visao_prod
            fmt_map_marca_st['Evolução Total %'] = fmt_var

            st.dataframe(
                df_marca_join[cols_exib_marca].style.format(fmt_map_marca_st).pipe(aplicar_cor_variacao, cols_var_marca), 
                use_container_width=True, height=400, hide_index=True
            )
            
            df_var_marca_export = df_marca_join[cols_exib_marca].copy()
            for c in cols_var_marca: df_var_marca_export[c] = df_var_marca_export[c].apply(fmt_var)

        buf_p = io.BytesIO()
        with pd.ExcelWriter(buf_p, engine='xlsxwriter') as w:
            df_prod_tabela[base_cols].to_excel(w, index=False, sheet_name='Matriz Portfólio 8020')
            if not df_log_excel_export.empty: df_log_excel_export.to_excel(w, index=False, sheet_name='Eficiência Logística Caixas')
            if not df_var_marca_export.empty: df_var_marca_export.to_excel(w, index=False, sheet_name='Evolutivo Marcas YoY')
        st.download_button("Exportar Produtos para Excel", data=buf_p.getvalue(), file_name="central_inteligencia_produtos.xlsx", mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet")

# ==============================================================================
# ABA 3 - INTELIGENCIA DE NEGOCIO
# ==============================================================================
with tab_inteligencia:
    if df_filtrado.empty:
        st.warning("Sem dados para os filtros aplicados.")
    else:
        op_visao_intel = st.radio("Metrica de Visualizacao Comercial (Aba Inteligencia)", ["Faturamento (R$)", "Volume (Caixas)"], horizontal=True, key="op_visao_intel")
        col_analise_intel = 'TVENDA' if op_visao_intel == "Faturamento (R$)" else 'QT'
        fmt_visao_intel = fmt_brl if op_visao_intel == "Faturamento (R$)" else fmt_inteiro

        colunas_meses_ib = sorted(df_filtrado['PERIODO_LIMPO'].unique(), key=delete_chave_cronologica)

        st.write(f"### Evolucao de {op_visao_intel} Mensal")
        serie_fat = df_filtrado.groupby('PERIODO_LIMPO')[col_analise_intel].sum().reindex(colunas_meses_ib).fillna(0)
        fat_fmt_list = [fmt_visao_intel(v) for v in serie_fat.values]
        fig_fat = go.Figure(go.Scatter(x=serie_fat.index.tolist(), y=serie_fat.values, mode='lines+markers', line=dict(color='#3b82f6', width=2), marker=dict(size=7, color='#60a5fa'), fill='tozeroy', fillcolor='rgba(59,130,246,0.10)', hovertemplate='<b>%{x}</b><br>' + f'{op_visao_intel.split(" ")[0]}: %{{customdata}}<extra></extra>', customdata=fat_fmt_list))
        layout_fat = base_layout(360)
        if col_analise_intel == 'TVENDA': layout_fat['yaxis'] = dict(gridcolor=PLOT_GRID, tickformat=',', tickprefix='R$ ')
        else: layout_fat['yaxis'] = dict(gridcolor=PLOT_GRID, tickformat=',')
        fig_fat.update_layout(**layout_fat)
        st.plotly_chart(fig_fat, use_container_width=True)

        if 'TLUCRO' in df_filtrado.columns:
            st.write("### Margem de Contribuicao por Mes (%)")
            serie_luc_m = df_filtrado.groupby('PERIODO_LIMPO')['TLUCRO'].sum().reindex(colunas_meses_ib).fillna(0)
            serie_fat_para_margem = df_filtrado.groupby('PERIODO_LIMPO')['TVENDA'].sum().reindex(colunas_meses_ib).fillna(0)
            serie_margem = (serie_luc_m / serie_fat_para_margem * 100).fillna(0)
            marg_fmt_list = [fmt_pct(v) for v in serie_margem.values]
            fig_marg = go.Figure(go.Scatter(x=serie_margem.index.tolist(), y=serie_margem.values, mode='lines+markers', line=dict(color='#10b981', width=2), marker=dict(size=7, color='#34d399'), fill='tozeroy', fillcolor='rgba(16,185,129,0.10)', hovertemplate='<b>%{x}</b><br>Margem: %{customdata}<extra></extra>', customdata=marg_fmt_list))
            layout_marg = base_layout(300); layout_marg['yaxis'] = dict(gridcolor=PLOT_GRID, ticksuffix='%')
            fig_marg.update_layout(**layout_marg)
            st.plotly_chart(fig_marg, use_container_width=True)

        st.markdown("---")
        st.write("### Clientes Novos vs Recorrentes por Mes")
        clientes_por_mes = df_filtrado.groupby(['PERIODO_LIMPO', 'CODCLI']).size().reset_index(name='pedidos')
        seen = set()
        novos_list, recorrentes_list = [], []
        for mes in colunas_meses_ib:
            clis_mes = set(clientes_por_mes[clientes_por_mes['PERIODO_LIMPO'] == mes]['CODCLI'])
            novos_list.append(len(clis_mes - seen))
            recorrentes_list.append(len(clis_mes & seen))
            seen |= clis_mes
        fig_nr = go.Figure()
        fig_nr.add_trace(go.Bar(name='Novos', x=colunas_meses_ib, y=novos_list, marker_color='#f59e0b', hovertemplate='<b>%{x}</b><br>Novos: %{y}<extra></extra>'))
        fig_nr.add_trace(go.Bar(name='Recorrentes', x=colunas_meses_ib, y=recorrentes_list, marker_color='#3b82f6', hovertemplate='<b>%{x}</b><br>Recorrentes: %{y}<extra></extra>'))
        layout_nr = base_layout(320); layout_nr['barmode'] = 'group'; layout_nr['legend'] = dict(orientation='h', yanchor='bottom', y=1.02, xanchor='right', x=1)
        fig_nr.update_layout(**layout_nr)
        st.plotly_chart(fig_nr, use_container_width=True)

        st.markdown("---")
        st.write(f"### Top 10 Clientes por {op_visao_intel.split(' ')[0]}")
        top10_cli = df_filtrado.groupby(['CODCLI', 'CLIENTE'])[col_analise_intel].sum().sort_values(ascending=False).head(10).reset_index()
        lbl_metrica = 'Faturamento' if col_analise_intel == 'TVENDA' else 'Volume'
        top10_cli.columns = ['Codigo', 'Cliente', lbl_metrica]
        lbl_fmt = 'Faturamento R$' if col_analise_intel == 'TVENDA' else 'Volume (Caixas)'
        top10_cli[lbl_fmt] = top10_cli[lbl_metrica].apply(fmt_visao_intel)
        soma_top = top10_cli[lbl_metrica].sum()
        top10_cli['% do Total'] = top10_cli[lbl_metrica].apply(lambda x: fmt_pct(x / soma_top * 100) if soma_top > 0 else '0.00%')
        st.dataframe(top10_cli[['Codigo', 'Cliente', lbl_fmt, '% do Total']], use_container_width=True, hide_index=True)
        
        top10_plot = top10_cli.sort_values(lbl_metrica, ascending=True)
        fig_top10 = go.Figure(go.Bar(x=top10_plot[lbl_metrica], y=top10_plot['Cliente'], orientation='h', marker_color='#6366f1', text=top10_plot[lbl_fmt], textposition='outside', hovertemplate='<b>%{y}</b><br>' + f'{lbl_metrica}: %{{customdata}}<extra></extra>', customdata=top10_plot[lbl_fmt]))
        layout_top10 = base_layout(400); layout_top10['xaxis'] = dict(gridcolor=PLOT_GRID, showticklabels=False, tickvals=[]).update(autorange="reversed")
        fig_top10.update_layout(**layout_top10)
        st.plotly_chart(fig_top10, use_container_width=True)

        buf_intel = io.BytesIO()
        with pd.ExcelWriter(buf_intel, engine='xlsxwriter') as w:
            pd.DataFrame({"Periodo": colunas_meses_ib, lbl_metrica: serie_fat.values}).to_excel(w, index=False, sheet_name="Evolucao Mensal")
            top10_cli.to_excel(w, index=False, sheet_name="Top 10 Clientes")
        st.download_button("Exportar Inteligencia de Negocio para Excel", data=buf_intel.getvalue(), file_name="rotina_8020_inteligencia.xlsx", mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet")

# ==============================================================================
# 🎯 4. SIMULADOR DE METAS (TOTALMENTE OPERACIONAL)
# ==============================================================================
with tab_metas:
    if df_filtrado_metas.empty:
        st.warning("Sem dados para simular metas com os filtros aplicados.")
    else:
        st.write("## Simulador de Metas Comerciais")
        st.caption("Defina metas de crescimento por Rede, Cliente ou Produto/Marca, em Faturamento ou Volume.")

        hoje = datetime.date.today()
        ano_vigente, mes_vigente = hoje.year, hoje.month
        periodo_vigente_tupla = (ano_vigente, mes_vigente)
        periodo_vigente_str = tupla_para_periodo(ano_vigente, mes_vigente)

        todos_periodos_base = sorted(df_filtrado_metas['PERIODO_LIMPO'].unique(), key=delete_chave_cronologica)
        tuplas_disponiveis = sorted([t for t in (periodo_para_tupla(p) for p in todos_periodos_base) if t is not None])

        if not tuplas_disponiveis:
            st.warning("Nao foi possivel identificar periodos validos na base.")
        else:
            ultimo_periodo_dados = tuplas_disponiveis[-1]

            st.write("### 1. Periodo da Meta")
            opcoes_periodo_meta = {
                "Mes Vigente (" + periodo_vigente_str + ")": (periodo_vigente_tupla, periodo_vigente_tupla),
                "Proximo Mes (" + tupla_para_periodo(*somar_meses(*periodo_vigente_tupla, 1)) + ")": (somar_meses(*periodo_vigente_tupla, 1), somar_meses(*periodo_vigente_tupla, 1)),
                "Proximo Trimestre": (somar_meses(*periodo_vigente_tupla, 1), somar_meses(*periodo_vigente_tupla, 3)),
                "Proximo Semestre": (somar_meses(*periodo_vigente_tupla, 1), somar_meses(*periodo_vigente_tupla, 6)),
                "Periodo Customizado": None,
            }

            col_p1, col_p2 = st.columns([2, 1])
            with col_p1: escolha_periodo = st.selectbox("Selecione o periodo alvo da meta", list(opcoes_periodo_meta.keys()))

            if escolha_periodo == "Periodo Customizado":
                with col_p2: n_meses_custom = st.number_input("Quantidade de meses a frente", min_value=1, max_value=24, value=1)
                inicio_meta = somar_meses(*periodo_vigente_tupla, 1)
                fim_meta = somar_meses(*periodo_vigente_tupla, int(n_meses_custom))
            else:
                inicio_meta, fim_meta = opcoes_periodo_meta[escolha_periodo]

            periodos_meta_tuplas = []
            cursor = inicio_meta
            while cursor <= fim_meta:
                periodos_meta_tuplas.append(cursor)
                if cursor == fim_meta: break
                cursor = somar_meses(*cursor, 1)
            periodos_meta_str = [tupla_para_periodo(a, m) for a, m in periodos_meta_tuplas]
            n_meses_meta = len(periodos_meta_tuplas)

            st.info("Periodo da meta: **" + (periodos_meta_str[0] if periodos_meta_str else "-") + ("" if n_meses_meta <= 1 else " ate " + periodos_meta_str[-1]) + "** (" + str(n_meses_meta) + " mes(es))")

            st.write("### 2. Base de Comparacao")
            base_comparacao = st.selectbox("Base de comparacao (sugestao automatica selecionada; pode trocar)", ["Mesmo Periodo no Ano Anterior", "Media dos Ultimos 3 Meses", "Media dos Ultimos 6 Meses"], index=0)

            def obter_periodos_base(periodos_meta_tuplas, base_comparacao, ultimo_periodo_dados):
                if base_comparacao == "Mesmo Periodo no Ano Anterior": return [(a - 1, m) for a, m in periodos_meta_tuplas]
                elif base_comparacao == "Media dos Ultimos 3 Meses":
                    fim = ultimo_periodo_dados; base = []; cursor = fim
                    for _ in range(3): base.append(cursor); cursor = somar_meses(*cursor, -1)
                    return sorted(base)
                else: 
                    fim = ultimo_periodo_dados; base = []; cursor = fim
                    for _ in range(6): base.append(cursor); cursor = somar_meses(*cursor, -1)
                    return sorted(base)

            periodos_base_tuplas = obter_periodos_base(periodos_meta_tuplas, base_comparacao, ultimo_periodo_dados)
            periodos_base_str = [tupla_para_periodo(a, m) for a, m in periodos_base_tuplas]
            st.caption("Periodos usados como base: " + ", ".join(periodos_base_str))

            st.markdown("---")
            st.write("### 3. Historico de Referencia")

            mes_passado_tupla = somar_meses(ano_vigente, mes_vigente, -1)
            ultimos_6_tuplas = sorted([somar_meses(*mes_passado_tupla, -i) for i in range(6)])
            colunas_hist_6m = [tupla_para_periodo(a, m) for a, m in ultimos_6_tuplas]

            periodos_meta_ano_ant_str = [tupla_para_periodo(a - 1, m) for a, m in periodos_meta_tuplas]
            col_ano_ant_nome = f"Ref. Ano Ant. ({'+'.join(periodos_meta_ano_ant_str)})"

            nivel_meta = st.radio("Nivel de definicao da meta", ["Rede de Clientes", "Cliente Individual", "Produto / Marca", "Produto Individual"], horizontal=True)
            metrica_meta = st.radio("Metrica base para a meta", ["Faturamento (R$)", "Volume (Caixas)"], horizontal=True)
            col_metrica = 'TVENDA' if metrica_meta == "Faturamento (R$)" else 'QT'
            fmt_metrica = fmt_brl if metrica_meta == "Faturamento (R$)" else fmt_inteiro

            if nivel_meta == "Rede de Clientes": chave_cols = ['CODREDE', 'REDE']; nome_chave = 'REDE'
            elif nivel_meta == "Cliente Individual": chave_cols = ['CODCLI', 'CLIENTE']; nome_chave = 'CLIENTE'
            elif nivel_meta == "Produto Individual": chave_cols = ['CODPROD', 'DESCRICAO']; nome_chave = 'DESCRICAO'
            else: chave_cols = ['MARCA']; nome_chave = 'MARCA'

            LIMITE_ITENS_NUVEM = 800
            qtde_itens = df_filtrado_metas[chave_cols[0]].nunique()

            if qtde_itens > LIMITE_ITENS_NUVEM:
                st.warning("⚠️ **Limite de Segurança do Servidor Atingido**")
                st.info(f"A seleção atual geraria uma tabela editável com **{qtde_itens} {nome_chave.title().replace('_', ' ')}s**.")
            else:
                pivot_hist = df_filtrado_metas.pivot_table(index=chave_cols, columns='PERIODO_LIMPO', values=col_metrica, aggfunc='sum').fillna(0)
                colunas_disponiveis_6m = [c for c in colunas_hist_6m if c in pivot_hist.columns]
                pivot_hist_exib = pivot_hist.reindex(columns=colunas_disponiveis_6m, fill_value=0).copy()
                
                cols_ref_ant = [c for c in periodos_meta_ano_ant_str if c in pivot_hist.columns]
                pivot_hist_exib[col_ano_ant_nome] = pivot_hist[cols_ref_ant].sum(axis=1) if cols_ref_ant else 0

                colunas_base_disponiveis = [c for c in periodos_base_str if c in pivot_hist.columns]
                if colunas_base_disponiveis:
                    valor_base_serie = pivot_hist[colunas_base_disponiveis].sum(axis=1) if base_comparacao == "Mesmo Periodo no Ano Anterior" else pivot_hist[colunas_base_disponiveis].mean(axis=1) * n_meses_meta
                else:
                    valor_base_serie = pd.Series(0, index=pivot_hist.index)

                col_base_meta = 'Base p/ Meta (' + base_comparacao + ')'
                pivot_hist_exib[col_base_meta] = valor_base_serie
                pivot_hist_exib = pivot_hist_exib.sort_values(col_base_meta, ascending=False).reset_index()

                if nivel_meta == "Rede de Clientes": pivot_hist_exib = pivot_hist_exib.rename(columns={'CODREDE': 'Codigo', 'REDE': 'Nome'})
                elif nivel_meta == "Cliente Individual": pivot_hist_exib = pivot_hist_exib.rename(columns={'CODCLI': 'Codigo', 'CLIENTE': 'Nome'})
                elif nivel_meta == "Produto Individual": pivot_hist_exib = pivot_hist_exib.rename(columns={'CODPROD': 'Codigo', 'DESCRICAO': 'Nome'})
                else: pivot_hist_exib = pivot_hist_exib.rename(columns={'MARCA': 'Nome'})
                col_nome_exib = 'Nome'

                pivot_hist_exib_top = pivot_hist_exib.copy()
                st.write("#### Historico (somente leitura)")
                cols_fmt_hist = colunas_disponiveis_6m + [col_ano_ant_nome, col_base_meta]
                
                def style_destaque_base(styler):
                    cols_destaque = [c for c in cols_fmt_hist if c in periodos_base_str or c == col_base_meta]
                    return styler.set_properties(subset=cols_destaque, **{'background-color': '#1e293b', 'color': '#38bdf8', 'font-weight': 'bold'}) if cols_destaque else styler

                st.dataframe(pivot_hist_exib_top.style.format({c: fmt_metrica for c in cols_fmt_hist}).pipe(style_destaque_base), use_container_width=True, height=350, hide_index=True)

                st.markdown("---")
                st.write("### 4. Definicao da Meta")
                
                chave_session_data = f"metas_data_{nivel_meta}_{metrica_meta}_{escolha_periodo}_{base_comparacao}"
                col_id_sessao = 'Codigo' if 'Codigo' in pivot_hist_exib_top.columns else col_nome_exib
                ids_atuais = pivot_hist_exib_top[col_id_sessao].astype(str).tolist()

                if chave_session_data not in st.session_state or st.session_state[chave_session_data]['Codigo'].astype(str).tolist() != ids_atuais:
                    st.session_state[chave_session_data] = pd.DataFrame({
                        'Codigo': pivot_hist_exib_top[col_id_sessao], 'Nome': pivot_hist_exib_top[col_nome_exib],
                        'Base Historica': pivot_hist_exib_top[col_base_meta], 'Base Fmt': pivot_hist_exib_top[col_base_meta].apply(fmt_metrica),
                        'Crescimento %': [0.0] * len(pivot_hist_exib_top), 'Valor Absoluto Meta': pivot_hist_exib_top[col_base_meta].round(2)
                    })

                col_input1, col_input2, _ = st.columns([2, 2, 4])
                with col_input1: pct_lote = st.number_input("Aplicar % de cresc. em lote:", value=0.0, step=1.0, format="%.2f")
                with col_input2:
                    st.write("")
                    if st.button("Aplicar Lote na Tabela"):
                        st.session_state[chave_session_data]['Crescimento %'] = pct_lote
                        st.session_state[chave_session_data]['Valor Absoluto Meta'] = (st.session_state[chave_session_data]['Base Historica'] * (1 + pct_lote / 100)).round(2)
                        st.rerun()

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

                st.data_editor(st.session_state[chave_session_data], key=f"ui_editor_{chave_session_data}", on_change=sync_editor, disabled=['Codigo', 'Nome', 'Base Fmt', 'Base Historica'], column_config={'Base Historica': None, 'Base Fmt': st.column_config.TextColumn("Base Histórica", disabled=True), 'Crescimento %': st.column_config.NumberColumn("Crescimento %", format="%.2f%%", step=1.0), 'Valor Absoluto Meta': st.column_config.NumberColumn("Valor Meta (Absoluto)", format="%.2f", step=100.0)}, use_container_width=True, height=400, hide_index=True)

                df_editado = st.session_state[chave_session_data].copy()
                df_editado['Meta Final'] = df_editado['Valor Absoluto Meta']

                df_quebra_cliente = pd.DataFrame()
                if nivel_meta == "Rede de Clientes":
                    st.markdown("---")
                    st.write("### 5. Quebra da Meta por Cliente (dentro de cada Rede)")
                    linhas_quebra = []
                    for _, inline_rede in df_editado.iterrows():
                        cod_rede = inline_rede['Codigo']
                        meta_rede = inline_rede['Meta Final']
                        if df_filtrado_metas[df_filtrado_metas['CODREDE'] == cod_rede].empty: continue
                        
                        hist_clientes = df_filtrado_metas[(df_filtrado_metas['CODREDE'] == cod_rede) & (df_filtrado_metas['PERIODO_LIMPO'].isin(colunas_base_disponiveis))].groupby(['CODCLI', 'CLIENTE'])[col_metrica].sum().div(max(len(colunas_base_disponiveis), 1))
                        soma_hist_rede = hist_clientes.sum()
                        for (cod_cli, nome_cli), valor_hist in hist_clientes.items():
                            participacao = (valor_hist / soma_hist_rede) if soma_hist_rede > 0 else (1 / len(hist_clientes))
                            linhas_quebra.append({'Cod. Rede': cod_rede, 'Rede': inline_rede['Nome'], 'Codigo Cliente': cod_cli, 'Cliente': nome_cli, 'Base Historica Cliente': valor_hist, 'Participacao na Rede %': participacao * 100, 'Meta Cliente': meta_rede * participacao})

                    if linhas_quebra:
                        df_quebra_cliente = pd.DataFrame(linhas_quebra)
                        st.dataframe(df_quebra_cliente.style.format({'Base Historica Cliente': fmt_metrica, 'Participacao na Rede %': fmt_pct, 'Meta Cliente': fmt_metrica}), use_container_width=True, height=350, hide_index=True)

                st.markdown("---")
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
                fig_meta.add_trace(go.Bar(name='Base Historica', y=df_grafico_meta['Nome'], x=df_grafico_meta['Base Historica'], orientation='h', marker_color='#475569', hovertemplate='<b>%{y}</b><br>Base: %{x:,.0f}<extra></extra>'))
                fig_meta.add_trace(go.Bar(name='Meta Definida', y=df_grafico_meta['Nome'], x=df_grafico_meta['Meta Final'], orientation='h', marker_color='#3b82f6', hovertemplate='<b>%{y}</b><br>Meta: %{x:,.0f}<extra></extra>'))
                layout_meta = base_layout(450); layout_meta['barmode'] = 'group'; layout_meta['yaxis'] = dict(gridcolor=PLOT_GRID, autorange='reversed')
                fig_meta.update_layout(**layout_meta)
                st.plotly_chart(fig_meta, use_container_width=True)

                df_export_resumo = pd.DataFrame({'Campo': ['Nivel da Meta', 'Metrica', 'Periodo da Meta', 'Base de Comparacao', 'Periodos Base Utilizados', 'Base Historica Total', 'Meta Total Definida', 'Crescimento Implicito Total'], 'Valor': [nivel_meta, metrica_meta, (periodos_meta_str[0] if periodos_meta_str else '-') + ('' if n_meses_meta <= 1 else ' ate ' + periodos_meta_str[-1]), base_comparacao, ", ".join(periodos_base_str), fmt_metrica(soma_base_total), fmt_metrica(soma_meta_total), fmt_pct(crescimento_total)]})
                df_export_detalhe = df_editado[['Codigo', 'Nome', 'Base Historica', 'Crescimento %', 'Meta Final']].copy()
                df_export_detalhe['Base Historica'] = df_export_detalhe['Base Historica'].apply(fmt_metrica); df_export_detalhe['Meta Final'] = df_export_detalhe['Meta Final'].apply(fmt_metrica); df_export_detalhe['Crescimento %'] = df_export_detalhe['Crescimento %'].apply(fmt_pct)

                buf_metas = io.BytesIO()
                with pd.ExcelWriter(buf_metas, engine='xlsxwriter') as w:
                    df_export_resumo.to_excel(w, index=False, sheet_name='Resumo da Meta')
                    df_export_detalhe.to_excel(w, index=False, sheet_name='Detalhamento')
                    if not df_quebra_cliente.empty:
                        df_quebra_excel = df_quebra_cliente.copy()
                        df_quebra_excel['Base Historica Cliente'] = df_quebra_excel['Base Historica Cliente'].apply(fmt_metrica); df_quebra_excel['Participacao na Rede %'] = df_quebra_excel['Participacao na Rede %'].apply(fmt_pct); df_quebra_excel['Meta Cliente'] = df_quebra_excel['Meta Cliente'].apply(fmt_metrica)
                        df_quebra_excel.to_excel(w, index=False, sheet_name='Quebra por Cliente')
                    df_hist_excel = pivot_hist_exib_top.copy()
                    for c in cols_fmt_hist:
                        if c in df_hist_excel.columns: df_hist_excel[c] = df_hist_excel[c].apply(fmt_metrica)
                    df_hist_excel.to_excel(w, index=False, sheet_name='Historico de Referencia')
                st.download_button("Exportar Meta para Excel", data=buf_metas.getvalue(), file_name=f"rotina_8020_meta_{nivel_meta.replace(' ', '_')}.xlsx", mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet")
