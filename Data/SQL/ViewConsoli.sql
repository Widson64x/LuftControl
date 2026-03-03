 SELECT 'FARMA'::text AS origem,
    r."Conta",
    r."Título Conta",
    r."Data",
    r."Numero",
    r."Descricao",
    r."Contra Partida - Credito",
    r."Filial",
    r."Centro de Custo",
    r."Item",
    r."Cod Cl. Valor",
    r."Debito",
    r."Credito",
    COALESCE(r."Debito", 0::double precision) - COALESCE(r."Credito", 0::double precision) AS "Saldo",
        CASE to_char(r."Data", 'MM'::text)
            WHEN '01'::text THEN 'Janeiro'::text
            WHEN '02'::text THEN 'Fevereiro'::text
            WHEN '03'::text THEN 'Março'::text
            WHEN '04'::text THEN 'Abril'::text
            WHEN '05'::text THEN 'Maio'::text
            WHEN '06'::text THEN 'Junho'::text
            WHEN '07'::text THEN 'Julho'::text
            WHEN '08'::text THEN 'Agosto'::text
            WHEN '09'::text THEN 'Setembro'::text
            WHEN '10'::text THEN 'Outubro'::text
            WHEN '11'::text THEN 'Novembro'::text
            WHEN '12'::text THEN 'Dezembro'::text
            ELSE NULL::text
        END AS "Mes",
    ccc_map."Tipo" AS "CC",
    ccc_map."Nome" AS "Nome do CC",
    cpcf_map."Denominacao" AS "Cliente",
    cpcf_map."Filial" AS "Filial Cliente",
    concat(
        CASE to_char(r."Data", 'MM'::text)
            WHEN '01'::text THEN 'Janeiro'::text
            WHEN '02'::text THEN 'Fevereiro'::text
            WHEN '03'::text THEN 'Março'::text
            WHEN '04'::text THEN 'Abril'::text
            WHEN '05'::text THEN 'Maio'::text
            WHEN '06'::text THEN 'Junho'::text
            WHEN '07'::text THEN 'Julho'::text
            WHEN '08'::text THEN 'Agosto'::text
            WHEN '09'::text THEN 'Setembro'::text
            WHEN '10'::text THEN 'Outubro'::text
            WHEN '11'::text THEN 'Novembro'::text
            WHEN '12'::text THEN 'Dezembro'::text
            ELSE NULL::text
        END, replace(r."Conta", '.'::text, ''::text)) AS "Chv_Mes_Conta",
    concat(
        CASE to_char(r."Data", 'MM'::text)
            WHEN '01'::text THEN 'Janeiro'::text
            WHEN '02'::text THEN 'Fevereiro'::text
            WHEN '03'::text THEN 'Março'::text
            WHEN '04'::text THEN 'Abril'::text
            WHEN '05'::text THEN 'Maio'::text
            WHEN '06'::text THEN 'Junho'::text
            WHEN '07'::text THEN 'Julho'::text
            WHEN '08'::text THEN 'Agosto'::text
            WHEN '09'::text THEN 'Setembro'::text
            WHEN '10'::text THEN 'Outubro'::text
            WHEN '11'::text THEN 'Novembro'::text
            WHEN '12'::text THEN 'Dezembro'::text
            ELSE NULL::text
        END, replace(r."Conta", '.'::text, ''::text), ccc_map."Tipo") AS "Chv_Mes_Conta_CC",
    concat(
        CASE to_char(r."Data", 'MM'::text)
            WHEN '01'::text THEN 'Janeiro'::text
            WHEN '02'::text THEN 'Fevereiro'::text
            WHEN '03'::text THEN 'Março'::text
            WHEN '04'::text THEN 'Abril'::text
            WHEN '05'::text THEN 'Maio'::text
            WHEN '06'::text THEN 'Junho'::text
            WHEN '07'::text THEN 'Julho'::text
            WHEN '08'::text THEN 'Agosto'::text
            WHEN '09'::text THEN 'Setembro'::text
            WHEN '10'::text THEN 'Outubro'::text
            WHEN '11'::text THEN 'Novembro'::text
            WHEN '12'::text THEN 'Dezembro'::text
            ELSE NULL::text
        END, ccc_map."Nome", replace(r."Conta", '.'::text, ''::text)) AS "Chv_Mes_NomeCC_Conta",
    concat(
        CASE to_char(r."Data", 'MM'::text)
            WHEN '01'::text THEN 'Janeiro'::text
            WHEN '02'::text THEN 'Fevereiro'::text
            WHEN '03'::text THEN 'Março'::text
            WHEN '04'::text THEN 'Abril'::text
            WHEN '05'::text THEN 'Maio'::text
            WHEN '06'::text THEN 'Junho'::text
            WHEN '07'::text THEN 'Julho'::text
            WHEN '08'::text THEN 'Agosto'::text
            WHEN '09'::text THEN 'Setembro'::text
            WHEN '10'::text THEN 'Outubro'::text
            WHEN '11'::text THEN 'Novembro'::text
            WHEN '12'::text THEN 'Dezembro'::text
            ELSE NULL::text
        END, ccc_map."Nome", replace(r."Conta", '.'::text, ''::text), ccc_map."Tipo") AS "Chv_Mes_NomeCC_Conta_CC",
    replace(r."Conta", '.'::text, ''::text) AS "Chv_Conta_Formatada",
    concat(
        CASE to_char(r."Data", 'MM'::text)
            WHEN '01'::text THEN 'Janeiro'::text
            WHEN '02'::text THEN 'Fevereiro'::text
            WHEN '03'::text THEN 'Março'::text
            WHEN '04'::text THEN 'Abril'::text
            WHEN '05'::text THEN 'Maio'::text
            WHEN '06'::text THEN 'Junho'::text
            WHEN '07'::text THEN 'Julho'::text
            WHEN '08'::text THEN 'Agosto'::text
            WHEN '09'::text THEN 'Setembro'::text
            WHEN '10'::text THEN 'Outubro'::text
            WHEN '11'::text THEN 'Novembro'::text
            WHEN '12'::text THEN 'Dezembro'::text
            ELSE NULL::text
        END, ccc_map."Nome", replace(r."Conta", '.'::text, ''::text), r."Centro de Custo") AS "Chv_Mes_NomeCC_Conta_CodCC"
   FROM "Dre_Schema"."Tb_CTL_Razao_Farma" r
     LEFT JOIN ( SELECT DISTINCT ON ("Tb_CTL_Cad_Centro_Custo"."Codigo") "Tb_CTL_Cad_Centro_Custo"."Codigo",
            "Tb_CTL_Cad_Centro_Custo"."Tipo",
            "Tb_CTL_Cad_Centro_Custo"."Nome"
           FROM "Dre_Schema"."Tb_CTL_Cad_Centro_Custo"
          ORDER BY "Tb_CTL_Cad_Centro_Custo"."Codigo") ccc_map ON ccc_map."Codigo"::text = r."Centro de Custo"::text
     LEFT JOIN ( SELECT DISTINCT ON ("Tb_CTL_Cad_Plano_Conta_Filial"."Item_Conta") "Tb_CTL_Cad_Plano_Conta_Filial"."Item_Conta",
            "Tb_CTL_Cad_Plano_Conta_Filial"."Denominacao",
            "Tb_CTL_Cad_Plano_Conta_Filial"."Filial"
           FROM "Dre_Schema"."Tb_CTL_Cad_Plano_Conta_Filial"
          ORDER BY "Tb_CTL_Cad_Plano_Conta_Filial"."Item_Conta") cpcf_map ON cpcf_map."Item_Conta"::text = r."Item"::text
UNION ALL
 SELECT 'FARMADIST'::text AS origem,
    r."Conta",
    r."Título Conta",
    r."Data",
    r."Numero",
    r."Descricao",
    r."Contra Partida - Credito",
    r."Filial",
    r."Centro de Custo",
    r."Item",
    r."Cod Cl. Valor",
    r."Debito",
    r."Credito",
    COALESCE(r."Debito", 0::double precision) - COALESCE(r."Credito", 0::double precision) AS "Saldo",
        CASE to_char(r."Data", 'MM'::text)
            WHEN '01'::text THEN 'Janeiro'::text
            WHEN '02'::text THEN 'Fevereiro'::text
            WHEN '03'::text THEN 'Março'::text
            WHEN '04'::text THEN 'Abril'::text
            WHEN '05'::text THEN 'Maio'::text
            WHEN '06'::text THEN 'Junho'::text
            WHEN '07'::text THEN 'Julho'::text
            WHEN '08'::text THEN 'Agosto'::text
            WHEN '09'::text THEN 'Setembro'::text
            WHEN '10'::text THEN 'Outubro'::text
            WHEN '11'::text THEN 'Novembro'::text
            WHEN '12'::text THEN 'Dezembro'::text
            ELSE NULL::text
        END AS "Mes",
    ccc_map2."Tipo" AS "CC",
    ccc_map2."Nome" AS "Nome do CC",
    cpcf_map2."Denominacao" AS "Cliente",
    cpcf_map2."Filial" AS "Filial Cliente",
    concat(
        CASE to_char(r."Data", 'MM'::text)
            WHEN '01'::text THEN 'Janeiro'::text
            WHEN '02'::text THEN 'Fevereiro'::text
            WHEN '03'::text THEN 'Março'::text
            WHEN '04'::text THEN 'Abril'::text
            WHEN '05'::text THEN 'Maio'::text
            WHEN '06'::text THEN 'Junho'::text
            WHEN '07'::text THEN 'Julho'::text
            WHEN '08'::text THEN 'Agosto'::text
            WHEN '09'::text THEN 'Setembro'::text
            WHEN '10'::text THEN 'Outubro'::text
            WHEN '11'::text THEN 'Novembro'::text
            WHEN '12'::text THEN 'Dezembro'::text
            ELSE NULL::text
        END, replace(r."Conta", '.'::text, ''::text)) AS "Chv_Mes_Conta",
    concat(
        CASE to_char(r."Data", 'MM'::text)
            WHEN '01'::text THEN 'Janeiro'::text
            WHEN '02'::text THEN 'Fevereiro'::text
            WHEN '03'::text THEN 'Março'::text
            WHEN '04'::text THEN 'Abril'::text
            WHEN '05'::text THEN 'Maio'::text
            WHEN '06'::text THEN 'Junho'::text
            WHEN '07'::text THEN 'Julho'::text
            WHEN '08'::text THEN 'Agosto'::text
            WHEN '09'::text THEN 'Setembro'::text
            WHEN '10'::text THEN 'Outubro'::text
            WHEN '11'::text THEN 'Novembro'::text
            WHEN '12'::text THEN 'Dezembro'::text
            ELSE NULL::text
        END, replace(r."Conta", '.'::text, ''::text), ccc_map2."Tipo") AS "Chv_Mes_Conta_CC",
    concat(
        CASE to_char(r."Data", 'MM'::text)
            WHEN '01'::text THEN 'Janeiro'::text
            WHEN '02'::text THEN 'Fevereiro'::text
            WHEN '03'::text THEN 'Março'::text
            WHEN '04'::text THEN 'Abril'::text
            WHEN '05'::text THEN 'Maio'::text
            WHEN '06'::text THEN 'Junho'::text
            WHEN '07'::text THEN 'Julho'::text
            WHEN '08'::text THEN 'Agosto'::text
            WHEN '09'::text THEN 'Setembro'::text
            WHEN '10'::text THEN 'Outubro'::text
            WHEN '11'::text THEN 'Novembro'::text
            WHEN '12'::text THEN 'Dezembro'::text
            ELSE NULL::text
        END, ccc_map2."Nome", replace(r."Conta", '.'::text, ''::text)) AS "Chv_Mes_NomeCC_Conta",
    concat(
        CASE to_char(r."Data", 'MM'::text)
            WHEN '01'::text THEN 'Janeiro'::text
            WHEN '02'::text THEN 'Fevereiro'::text
            WHEN '03'::text THEN 'Março'::text
            WHEN '04'::text THEN 'Abril'::text
            WHEN '05'::text THEN 'Maio'::text
            WHEN '06'::text THEN 'Junho'::text
            WHEN '07'::text THEN 'Julho'::text
            WHEN '08'::text THEN 'Agosto'::text
            WHEN '09'::text THEN 'Setembro'::text
            WHEN '10'::text THEN 'Outubro'::text
            WHEN '11'::text THEN 'Novembro'::text
            WHEN '12'::text THEN 'Dezembro'::text
            ELSE NULL::text
        END, ccc_map2."Nome", replace(r."Conta", '.'::text, ''::text), ccc_map2."Tipo") AS "Chv_Mes_NomeCC_Conta_CC",
    replace(r."Conta", '.'::text, ''::text) AS "Chv_Conta_Formatada",
    concat(
        CASE to_char(r."Data", 'MM'::text)
            WHEN '01'::text THEN 'Janeiro'::text
            WHEN '02'::text THEN 'Fevereiro'::text
            WHEN '03'::text THEN 'Março'::text
            WHEN '04'::text THEN 'Abril'::text
            WHEN '05'::text THEN 'Maio'::text
            WHEN '06'::text THEN 'Junho'::text
            WHEN '07'::text THEN 'Julho'::text
            WHEN '08'::text THEN 'Agosto'::text
            WHEN '09'::text THEN 'Setembro'::text
            WHEN '10'::text THEN 'Outubro'::text
            WHEN '11'::text THEN 'Novembro'::text
            WHEN '12'::text THEN 'Dezembro'::text
            ELSE NULL::text
        END, ccc_map2."Nome", replace(r."Conta", '.'::text, ''::text), r."Centro de Custo") AS "Chv_Mes_NomeCC_Conta_CodCC"
   FROM "Dre_Schema"."Tb_CTL_Razao_FarmaDist" r
     LEFT JOIN ( SELECT DISTINCT ON ("Tb_CTL_Cad_Centro_Custo"."Codigo") "Tb_CTL_Cad_Centro_Custo"."Codigo",
            "Tb_CTL_Cad_Centro_Custo"."Tipo",
            "Tb_CTL_Cad_Centro_Custo"."Nome"
           FROM "Dre_Schema"."Tb_CTL_Cad_Centro_Custo"
          ORDER BY "Tb_CTL_Cad_Centro_Custo"."Codigo") ccc_map2 ON ccc_map2."Codigo"::text = r."Centro de Custo"::text
     LEFT JOIN ( SELECT DISTINCT ON ("Tb_CTL_Cad_Plano_Conta_Filial"."Item_Conta") "Tb_CTL_Cad_Plano_Conta_Filial"."Item_Conta",
            "Tb_CTL_Cad_Plano_Conta_Filial"."Denominacao",
            "Tb_CTL_Cad_Plano_Conta_Filial"."Filial"
           FROM "Dre_Schema"."Tb_CTL_Cad_Plano_Conta_Filial"
          ORDER BY "Tb_CTL_Cad_Plano_Conta_Filial"."Item_Conta") cpcf_map2 ON cpcf_map2."Item_Conta"::text = r."Item"::text
UNION ALL
 SELECT 'INTEC'::text AS origem,
    r."Conta",
    r."Título Conta",
    r."Data",
    r."Numero",
    r."Descricao",
    r."Contra Partida - Credito",
    r."Filial",
    r."Centro de Custo",
    r."Item",
    r."Cod Cl. Valor",
    r."Debito",
    r."Credito",
    COALESCE(r."Debito", 0::double precision) - COALESCE(r."Credito", 0::double precision) AS "Saldo",
        CASE to_char(r."Data", 'MM'::text)
            WHEN '01'::text THEN 'Janeiro'::text
            WHEN '02'::text THEN 'Fevereiro'::text
            WHEN '03'::text THEN 'Março'::text
            WHEN '04'::text THEN 'Abril'::text
            WHEN '05'::text THEN 'Maio'::text
            WHEN '06'::text THEN 'Junho'::text
            WHEN '07'::text THEN 'Julho'::text
            WHEN '08'::text THEN 'Agosto'::text
            WHEN '09'::text THEN 'Setembro'::text
            WHEN '10'::text THEN 'Outubro'::text
            WHEN '11'::text THEN 'Novembro'::text
            WHEN '12'::text THEN 'Dezembro'::text
            ELSE NULL::text
        END AS "Mes",
    ccc_map3."Tipo" AS "CC",
    ccc_map3."Nome" AS "Nome do CC",
    cpcf_map3."Denominacao" AS "Cliente",
    cpcf_map3."Filial" AS "Filial Cliente",
    concat(
        CASE to_char(r."Data", 'MM'::text)
            WHEN '01'::text THEN 'Janeiro'::text
            WHEN '02'::text THEN 'Fevereiro'::text
            WHEN '03'::text THEN 'Março'::text
            WHEN '04'::text THEN 'Abril'::text
            WHEN '05'::text THEN 'Maio'::text
            WHEN '06'::text THEN 'Junho'::text
            WHEN '07'::text THEN 'Julho'::text
            WHEN '08'::text THEN 'Agosto'::text
            WHEN '09'::text THEN 'Setembro'::text
            WHEN '10'::text THEN 'Outubro'::text
            WHEN '11'::text THEN 'Novembro'::text
            WHEN '12'::text THEN 'Dezembro'::text
            ELSE NULL::text
        END, replace(r."Conta", '.'::text, ''::text)) AS "Chv_Mes_Conta",
    concat(
        CASE to_char(r."Data", 'MM'::text)
            WHEN '01'::text THEN 'Janeiro'::text
            WHEN '02'::text THEN 'Fevereiro'::text
            WHEN '03'::text THEN 'Março'::text
            WHEN '04'::text THEN 'Abril'::text
            WHEN '05'::text THEN 'Maio'::text
            WHEN '06'::text THEN 'Junho'::text
            WHEN '07'::text THEN 'Julho'::text
            WHEN '08'::text THEN 'Agosto'::text
            WHEN '09'::text THEN 'Setembro'::text
            WHEN '10'::text THEN 'Outubro'::text
            WHEN '11'::text THEN 'Novembro'::text
            WHEN '12'::text THEN 'Dezembro'::text
            ELSE NULL::text
        END, replace(r."Conta", '.'::text, ''::text), ccc_map3."Tipo") AS "Chv_Mes_Conta_CC",
    concat(
        CASE to_char(r."Data", 'MM'::text)
            WHEN '01'::text THEN 'Janeiro'::text
            WHEN '02'::text THEN 'Fevereiro'::text
            WHEN '03'::text THEN 'Março'::text
            WHEN '04'::text THEN 'Abril'::text
            WHEN '05'::text THEN 'Maio'::text
            WHEN '06'::text THEN 'Junho'::text
            WHEN '07'::text THEN 'Julho'::text
            WHEN '08'::text THEN 'Agosto'::text
            WHEN '09'::text THEN 'Setembro'::text
            WHEN '10'::text THEN 'Outubro'::text
            WHEN '11'::text THEN 'Novembro'::text
            WHEN '12'::text THEN 'Dezembro'::text
            ELSE NULL::text
        END, ccc_map3."Nome", replace(r."Conta", '.'::text, ''::text)) AS "Chv_Mes_NomeCC_Conta",
    concat(
        CASE to_char(r."Data", 'MM'::text)
            WHEN '01'::text THEN 'Janeiro'::text
            WHEN '02'::text THEN 'Fevereiro'::text
            WHEN '03'::text THEN 'Março'::text
            WHEN '04'::text THEN 'Abril'::text
            WHEN '05'::text THEN 'Maio'::text
            WHEN '06'::text THEN 'Junho'::text
            WHEN '07'::text THEN 'Julho'::text
            WHEN '08'::text THEN 'Agosto'::text
            WHEN '09'::text THEN 'Setembro'::text
            WHEN '10'::text THEN 'Outubro'::text
            WHEN '11'::text THEN 'Novembro'::text
            WHEN '12'::text THEN 'Dezembro'::text
            ELSE NULL::text
        END, ccc_map3."Nome", replace(r."Conta", '.'::text, ''::text), ccc_map3."Tipo") AS "Chv_Mes_NomeCC_Conta_CC",
    replace(r."Conta", '.'::text, ''::text) AS "Chv_Conta_Formatada",
    concat(
        CASE to_char(r."Data", 'MM'::text)
            WHEN '01'::text THEN 'Janeiro'::text
            WHEN '02'::text THEN 'Fevereiro'::text
            WHEN '03'::text THEN 'Março'::text
            WHEN '04'::text THEN 'Abril'::text
            WHEN '05'::text THEN 'Maio'::text
            WHEN '06'::text THEN 'Junho'::text
            WHEN '07'::text THEN 'Julho'::text
            WHEN '08'::text THEN 'Agosto'::text
            WHEN '09'::text THEN 'Setembro'::text
            WHEN '10'::text THEN 'Outubro'::text
            WHEN '11'::text THEN 'Novembro'::text
            WHEN '12'::text THEN 'Dezembro'::text
            ELSE NULL::text
        END, ccc_map3."Nome", replace(r."Conta", '.'::text, ''::text), r."Centro de Custo") AS "Chv_Mes_NomeCC_Conta_CodCC"
   FROM "Dre_Schema"."Tb_CTL_Razao_Intec" r
     LEFT JOIN ( SELECT DISTINCT ON ("Tb_CTL_Cad_Centro_Custo"."Codigo") "Tb_CTL_Cad_Centro_Custo"."Codigo",
            "Tb_CTL_Cad_Centro_Custo"."Tipo",
            "Tb_CTL_Cad_Centro_Custo"."Nome"
           FROM "Dre_Schema"."Tb_CTL_Cad_Centro_Custo"
          ORDER BY "Tb_CTL_Cad_Centro_Custo"."Codigo") ccc_map3 ON ccc_map3."Codigo"::text = r."Centro de Custo"::text
     LEFT JOIN ( SELECT DISTINCT ON ("Tb_CTL_Cad_Plano_Conta_Filial"."Item_Conta") "Tb_CTL_Cad_Plano_Conta_Filial"."Item_Conta",
            "Tb_CTL_Cad_Plano_Conta_Filial"."Denominacao",
            "Tb_CTL_Cad_Plano_Conta_Filial"."Filial"
           FROM "Dre_Schema"."Tb_CTL_Cad_Plano_Conta_Filial"
          ORDER BY "Tb_CTL_Cad_Plano_Conta_Filial"."Item_Conta") cpcf_map3 ON cpcf_map3."Item_Conta"::text = r."Item"::text;