# import re
import logging

from odoo import fields, models, api, _     #, tools
from .allss_funtions import account_analytic_def
# import odoo.addons.decimal_precision as dp

_logger = logging.getLogger(__name__)


class BalanceAccountAnalytic(models.Model):
    _name = "allss.balance.account.analytic"
    _description = "Balancete Estruturado Contas Analiticas"
    _order = "allss_company_id, allss_date, allss_account_analytic_id, allss_account_id"

    allss_company_id = fields.Many2one('res.company', string='Empresa', store=True, index=True)

    allss_parent_id_6 = fields.Many2one('account.group', string='1º Nível', store=True, index=True)
    allss_parent_id_5 = fields.Many2one('account.group', string='2º Nível', store=True, index=True)
    allss_parent_id_4 = fields.Many2one('account.group', string='3º Nível', store=True, index=True)
    allss_parent_id_3 = fields.Many2one('account.group', string='4º Nível', store=True, index=True)
    allss_group_id = fields.Many2one('account.group', string='5º Nível', store=True, index=True)

    allss_account_id = fields.Many2one('account.account', string='Conta', store=True, index=True)

    allss_account_analytic_id = fields.Many2one('account.analytic.account', string='Conta Analítica', store=True,index=True)
    allss_analytic_plan_id = fields.Many2one('account.analytic.plan', string='Plano Analítico', store=True,index=True)

    allss_date = fields.Date(string="Data", store=True, index=True)

    allss_previous_balance = fields.Float(string="Saldo Anterior", store=True, index=True, digits='Account Balance')
    allss_debit = fields.Float(string="Débito", store=True, index=True, digits='Account Balance')
    allss_credit = fields.Float(string="Crédito", store=True, index=True, digits='Account Balance')
    allss_final_balance = fields.Float(string="Saldo Atual", store=True, index=True, digits='Account Balance')


    @staticmethod
    def _sql_code_and_params(sql_obj):
        """
        Recebe um odoo.tools.sql.SQL (ou string) e devolve (sql_string, params_list).
        """
        if not sql_obj:
            return "", []

        # Em Odoo 18, SQL tem .code e .params
        code = getattr(sql_obj, "code", None)
        params = getattr(sql_obj, "params", None)

        if code is None:
            code = str(sql_obj)

        if params is None:
            params = []
        elif not isinstance(params, (list, tuple)):
            params = [params]

        return code, list(params)



    @api.model
    def read_group(self, domain, fields, groupby, offset=0, limit=None, orderby=False, lazy=True):
        required = {'allss_previous_balance', 'allss_debit', 'allss_credit', 'allss_final_balance'}
        fields_to_read = list(set(fields or []) | required)

        result = super().read_group(domain, fields_to_read, groupby,
                                    offset=offset, limit=limit, orderby=orderby, lazy=lazy)
        if not result or not fields:
            return result

        table = self._table  # "allss_balance_account_analytic"

        for group_line in result:
            gdom = group_line.get('__domain')
            if not gdom:
                continue

            cnt = group_line.get('allss_account_analytic_id_count')
            do_calc = (cnt is None) or (cnt > 1)

            if not do_calc:
                previous = group_line.get('allss_previous_balance') or 0.0
                group_line['allss_final_balance'] = previous + (group_line.get('allss_debit') or 0.0) - (group_line.get('allss_credit') or 0.0)
                continue

            # Compila domínio do grupo para SQL (Query + SQL objects)
            query = self._where_calc(gdom)
            self._apply_ir_rules(query, 'read')

            from_code, from_params = self._sql_code_and_params(query.from_clause)
            where_code, where_params = self._sql_code_and_params(query.where_clause)

            # from_params normalmente vazio; where_params contém os %s do where_code
            params = []
            params.extend(from_params)
            params.extend(where_params)

            where_sql = f"WHERE {where_code}" if where_code else ""

            # Replica a lógica do Odoo 12 (saldo inicial = soma do 1º saldo por (company, account))
            sql = f"""
                SELECT COALESCE(SUM(x.prev), 0) AS allss_previous_balance
                FROM (
                    SELECT DISTINCT ON ("{table}"."allss_company_id", "{table}"."allss_account_analytic_id", "{table}"."allss_account_id")
                        "{table}"."allss_company_id",
                        "{table}"."allss_account_id",
                        "{table}"."allss_previous_balance" AS prev
                    FROM {from_code}
                    {where_sql}
                    ORDER BY
                        "{table}"."allss_company_id",
                        "{table}"."allss_account_analytic_id",
                        "{table}"."allss_account_id",
                        "{table}"."allss_date" ASC,
                        "{table}"."id" ASC
                ) x
            """

            self.env.cr.execute("SET LOCAL work_mem = '8MB'")
            self.env.cr.execute("SET LOCAL max_parallel_workers_per_gather = 0")
            self.env.cr.execute("SET LOCAL enable_hashagg = off")
            self.env.cr.execute("SET LOCAL enable_hashjoin = off")
            self.env.cr.execute(sql, params)
            previous = (self.env.cr.fetchone() or [0.0])[0] or 0.0

            group_line['allss_previous_balance'] = previous
            group_line['allss_final_balance'] = (
                previous
                + (group_line.get('allss_debit') or 0.0)
                - (group_line.get('allss_credit') or 0.0)
            )

        return result



    # @api.model
    # def read_group(self, domain, fields, groupby, offset=0, limit=None, orderby=False, lazy=True):
    #     required = {'allss_previous_balance', 'allss_debit', 'allss_credit', 'allss_final_balance'}
    #     fields_to_read = list(set(fields or []) | required)

    #     result = super().read_group(
    #         domain, fields_to_read, groupby,
    #         offset=offset, limit=limit, orderby=orderby, lazy=lazy
    #     )
    #     if not result or not fields:
    #         return result

    #     table = self._table  # allss_balance_account_analytic

    #     for group_line in result:
    #         gdom = group_line.get('__domain')
    #         if not gdom:
    #             continue

    #         # Se o super trouxe count, você pode usar como “atalho”
    #         # (ajuste o campo conforme seu groupby real; às vezes é allss_account_id_count)
    #         cnt = group_line.get('allss_account_analytic_id_count')
    #         do_calc = (cnt is None) or (cnt > 1)

    #         if not do_calc:
    #             previous = group_line.get('allss_previous_balance') or 0.0
    #             group_line['allss_final_balance'] = previous + (group_line.get('allss_debit') or 0.0) - (group_line.get('allss_credit') or 0.0)
    #             continue

    #        self.env.cr.execute("SET LOCAL work_mem = '8MB'")
    #        self.env.cr.execute("SET LOCAL max_parallel_workers_per_gather = 0")
    #        self.env.cr.execute("SET LOCAL enable_hashagg = off")
    #        self.env.cr.execute("SET LOCAL enable_hashjoin = off")

    #         # Converte o domínio do grupo em IDs (evita alias/joins do from_clause)
    #         ids = self.with_context(prefetch_fields=False)._search(gdom)
    #         if not ids:
    #             previous = 0.0
    #         else:
    #             self.env.cr.execute(f"""
    #                 SELECT COALESCE(SUM(x.prev), 0) AS allss_previous_balance
    #                 FROM (
    #                     SELECT DISTINCT ON (allss_company_id, allss_account_analytic_id, allss_account_id)
    #                         allss_company_id,
    #                         allss_account_analytic_id,
    #                         allss_account_id,
    #                         allss_previous_balance AS prev
    #                     FROM {table}
    #                     WHERE id = ANY(%s)
    #                     ORDER BY
    #                         allss_company_id,
    #                         allss_account_analytic_id,
    #                         allss_account_id,
    #                         allss_date ASC,
    #                         id ASC
    #                 ) x
    #             """, (list(ids),))
    #             previous = (self.env.cr.fetchone() or [0.0])[0] or 0.0

    #         group_line['allss_previous_balance'] = previous
    #         group_line['allss_final_balance'] = (
    #             previous
    #             + (group_line.get('allss_debit') or 0.0)
    #             - (group_line.get('allss_credit') or 0.0)
    #         )

    #     return result


     
    def open_document(self, options=None, params=None):

        domain = ['&',
                  ('date', '=', self.allss_date),
                  ('account_id', '=', self.allss_account_id.id)
                  ]

        dict_ret = {'type': 'ir.actions.act_window',
                    'name': f'Balancete Estruturado - Conta: {self.allss_account_id.id} - Data: {self.allss_date}',
                    'res_model': 'account.move.line',
                    # 'view_type': 'tree',
                    'view_mode': 'list,pivot,kanban,graph,form',
                    'domain': domain
                    }

        return dict_ret




    def _ensure_allss_indexes_for_balancete_analytic(self, concurrently=True):
        """
        Garante os índices necessários para performance e concorrência do balancete analítico.
        """
        cr = self._cr
        suffix = " CONCURRENTLY" if concurrently else ""

        statements = [
            # ============================================================
            # 1) INTEGRIDADE / CONCORRÊNCIA
            #    Garante 1 registro no dia 01 por (company, account, analytic, date).
            #    Permite múltiplos registros nos demais dias.
            # ============================================================
            f"""
            CREATE UNIQUE INDEX{suffix} IF NOT EXISTS l10n_br_allss_bal_an_uniq_m01
            ON allss_balance_account_analytic (
                allss_company_id,
                allss_account_id,
                allss_account_analytic_id,
                allss_date
            )
            WHERE EXTRACT(day FROM allss_date) = 1;
            """,

            # ============================================================
            # 2) PERFORMANCE - allss_balance_account_analytic
            #    (a) Para "pegar último registro" por company/account/analytic:
            #        usado em LATERAL (saldo anterior / último saldo).
            # ============================================================
            f"""
            CREATE INDEX{suffix} IF NOT EXISTS l10n_br_allss_bal_an_ccaa_date_desc
            ON allss_balance_account_analytic (
                allss_company_id,
                allss_account_id,
                allss_account_analytic_id,
                allss_date DESC,
                id DESC
            );
            """,

            #    (b) Para "pegar primeiro registro" por company/account/analytic:
            #        útil se você usar DISTINCT ON / ORDER BY date,id ASC em agregações.
            f"""
            CREATE INDEX{suffix} IF NOT EXISTS l10n_br_allss_bal_an_ccaa_date_id
            ON allss_balance_account_analytic (
                allss_company_id,
                allss_account_id,
                allss_account_analytic_id,
                allss_date,
                id
            );
            """,

            #    (c) Filtros comuns por data
            f"""
            CREATE INDEX{suffix} IF NOT EXISTS l10n_br_allss_bal_an_date
            ON allss_balance_account_analytic (allss_date);
            """,

            #    (d) Filtros comuns por hierarquia/grupo
            f"""
            CREATE INDEX{suffix} IF NOT EXISTS l10n_br_allss_bal_an_parent6
            ON allss_balance_account_analytic (allss_parent_id_6);
            """,
            f"""
            CREATE INDEX{suffix} IF NOT EXISTS l10n_br_allss_bal_an_parent5
            ON allss_balance_account_analytic (allss_parent_id_5);
            """,
            f"""
            CREATE INDEX{suffix} IF NOT EXISTS l10n_br_allss_bal_an_parent4
            ON allss_balance_account_analytic (allss_parent_id_4);
            """,
            f"""
            CREATE INDEX{suffix} IF NOT EXISTS l10n_br_allss_bal_an_parent3
            ON allss_balance_account_analytic (allss_parent_id_3);
            """,
            f"""
            CREATE INDEX{suffix} IF NOT EXISTS l10n_br_allss_bal_an_group
            ON allss_balance_account_analytic (allss_group_id);
            """,

            # ============================================================
            # 3) PERFORMANCE - account_move_line / account_move
            #    Usado no execute_sql_analytic (joins posted, filtros, agregações).
            # ============================================================
            f"""
            CREATE INDEX{suffix} IF NOT EXISTS l10n_br_allss_aml_move_id
            ON account_move_line (move_id);
            """,

            f"""
            CREATE INDEX{suffix} IF NOT EXISTS l10n_br_allss_aml_company_account_date
            ON account_move_line (company_id, account_id, date);
            """,

            # posted + company no move
            f"""
            CREATE INDEX{suffix} IF NOT EXISTS l10n_br_allss_am_state_company_id
            ON account_move (state, company_id, id);
            """,

            # Opcional (geralmente ajuda se você tem MUITO dist e faz varreduras/filtragens por presença)
            # Não acelera jsonb_each em si, mas pode ajudar em alguns planos.
            f"""
            CREATE INDEX{suffix} IF NOT EXISTS l10n_br_allss_aml_analytic_dist_notnull
            ON account_move_line (id)
            WHERE analytic_distribution IS NOT NULL AND analytic_distribution::text <> '{{}}';
            """,

            # ============================================================
            # 4) PERFORMANCE - allss_balance_account_analytic
            #    (a) o res_group.
            # ============================================================
            f"""
            CREATE INDEX{suffix} IF NOT EXISTS l10n_br_allss_bal_analytic_group_first
            ON allss_balance_account_analytic (
                allss_company_id,
                allss_account_analytic_id,
                allss_account_id,
                allss_date,
                id
            );
            """,
        ]

        for stmt in statements:
            cr.execute(stmt)




    def ensure_indexes_then_recalc_analytic(self, index_creation_mode=False, fallback_non_concurrently=False):
        cr = self._cr

        cr.execute("SELECT pg_advisory_lock(hashtext('allss_balance_account_analytic_recalc'));")
        try:
            if index_creation_mode:
                # CREATE INDEX CONCURRENTLY exige fora de transação
                cr.commit()
                try:
                    self._ensure_allss_indexes_for_balancete_analytic(concurrently=True)
                    cr.commit()
                except Exception:
                    cr.rollback()
                    if fallback_non_concurrently:
                        _logger.warning("Fallback sem CONCURRENTLY habilitado; pode bloquear escrita.")
                        self._ensure_allss_indexes_for_balancete_analytic(concurrently=False)
                        cr.commit()
                    else:
                        raise

            # Rodar em uma transação única (tudo ou nada)
            with cr.savepoint():
                # Execute primeiro a recriação completa
                self.execute_sql_analytic(autocommit=False)

                # Depois insere “dia 01” do mês atual quando faltar
                self.init_account_analytic(autocommit=False)

            cr.commit()

        except Exception:
            cr.rollback()
            raise

        finally:
            try:
                cr.execute("SELECT pg_advisory_unlock(hashtext('allss_balance_account_analytic_recalc'));")
            except Exception:
                _logger.exception("Falha ao liberar advisory lock.")




    def execute_sql_analytic(self, autocommit=False):
        """
        Recria toda a tabela allss_balance_account_analytic (por DIA),
        consistente com a estrutura validada do Balancete Estruturado (ctb via code_store),
        incluindo distribuição analítica com normalização e fallback para analítica default.

        Blindagem contra sujeira:
        - ignora moves posted sem company_id
        - company_id/date vêm preferencialmente do AML; se nulos, herda do Move
        """
        cr = self._cr

        # Defina o default analytic id (conforme sua função)
        default_analytic_id = int(account_analytic_def(self)[0] or 0)
        if not default_analytic_id:
            # Se você realmente precisa de um default SEMPRE, force aqui.
            # Caso contrário, levante erro para não mascarar inconsistência.
            raise ValueError("account_analytic_def() retornou vazio/0. Defina uma analítica default válida.")

        cr.execute("SET LOCAL work_mem = '8MB'")
        cr.execute("SET LOCAL max_parallel_workers_per_gather = 0")
        cr.execute("SET LOCAL enable_hashagg = off")
        cr.execute("SET LOCAL enable_hashjoin = off")

        # Recria do zero
        cr.execute("TRUNCATE TABLE allss_balance_account_analytic RESTART IDENTITY CASCADE;")

        sql = f"""
                INSERT INTO allss_balance_account_analytic (
                    create_uid, create_date, write_uid, write_date,
                    allss_company_id,
                    allss_parent_id_6,
                    allss_parent_id_5,
                    allss_parent_id_4,
                    allss_parent_id_3,
                    allss_group_id,
                    allss_account_id,
                    allss_account_analytic_id,
                    allss_analytic_plan_id,
                    allss_date,
                    allss_previous_balance,
                    allss_debit,
                    allss_credit,
                    allss_final_balance
                )
                WITH
                params AS (
                    SELECT {default_analytic_id}::int AS default_analytic_id
                ),

                -- ============================================================
                -- 1) Mapeamento conta->grupo (MESMA abordagem do Estruturado validado)
                -- ============================================================
                ctb AS (
                    SELECT
                        g.company_id        AS company_id,
                        g.id                AS group_id,
                        c.id                AS account_id
                    FROM account_account c
                    CROSS JOIN LATERAL jsonb_each_text(COALESCE(c.code_store, '{{}}'::jsonb)) AS j(key, value)
                    JOIN LATERAL (
                        SELECT g.*
                        FROM account_group g
                        WHERE g.company_id::text = j.key
                        AND LEFT(j.value, LENGTH(g.code_prefix_start)) = g.code_prefix_start
                        ORDER BY LENGTH(g.code_prefix_start) DESC
                        LIMIT 1
                    ) g ON TRUE
                ),

                -- ============================================================
                -- 2) AML posted (blindado contra sujeira)
                --    - sempre filtra posted
                --    - exige am.company_id (senão gera lixo sem company)
                --    - company_id/date herdam do move se AML vier nulo
                -- ============================================================
                aml_posted AS (
                    SELECT
                        aml.id,
                        COALESCE(aml.company_id, am.company_id)      AS company_id,
                        aml.account_id                               AS account_id,
                        COALESCE(aml.date, am.date)                  AS dt,
                        aml.debit                                    AS debit,
                        aml.credit                                   AS credit,
                        aml.analytic_distribution::jsonb              AS adist
                    FROM account_move_line aml
                    JOIN account_move am
                    ON am.id = aml.move_id
                    AND am.state = 'posted'
                    WHERE am.company_id IS NOT NULL
                    AND COALESCE(aml.company_id, am.company_id) IS NOT NULL
                    AND COALESCE(aml.date, am.date) IS NOT NULL
                    AND aml.account_id IS NOT NULL
                ),

                -- ============================================================
                -- 3) Explode distribuição (somente onde há JSON válido e não vazio)
                -- ============================================================
                dist_raw AS (
                    SELECT
                        a.id               AS aml_id,
                        a.company_id       AS company_id,
                        a.account_id       AS account_id,
                        a.dt               AS dt,
                        (kv.key)::int      AS analytic_id,
                        CASE
                            WHEN (kv.value)::numeric > 1 THEN (kv.value)::numeric / 100.0
                            ELSE (kv.value)::numeric
                        END                AS w
                    FROM aml_posted a
                    JOIN LATERAL jsonb_each(a.adist) kv(key, value)
                    ON a.adist IS NOT NULL
                    AND a.adist <> '{{}}'::jsonb
                ),
                dist_sum AS (
                    SELECT aml_id, SUM(w) AS w_sum
                    FROM dist_raw
                    GROUP BY aml_id
                ),
                dist_norm AS (
                    SELECT
                        r.aml_id,
                        r.company_id,
                        r.account_id,
                        r.dt,
                        r.analytic_id,
                        CASE
                            WHEN s.w_sum IS NULL OR s.w_sum = 0 THEN NULL
                            ELSE r.w / s.w_sum
                        END AS w_norm
                    FROM dist_raw r
                    JOIN dist_sum s ON s.aml_id = r.aml_id
                ),
                dist_alloc AS (
                    SELECT
                        n.company_id,
                        n.account_id,
                        n.analytic_id,
                        n.dt,
                        SUM(a.debit  * n.w_norm) AS debit,
                        SUM(a.credit * n.w_norm) AS credit
                    FROM dist_norm n
                    JOIN aml_posted a ON a.id = n.aml_id
                    WHERE n.w_norm IS NOT NULL
                    GROUP BY n.company_id, n.account_id, n.analytic_id, n.dt
                ),

                -- ============================================================
                -- 4) Linhas sem distribuição => 100% na analítica default
                -- ============================================================
                nodist AS (
                    SELECT
                        a.company_id,
                        a.account_id,
                        p.default_analytic_id AS analytic_id,
                        a.dt,
                        SUM(a.debit)  AS debit,
                        SUM(a.credit) AS credit
                    FROM aml_posted a
                    CROSS JOIN params p
                    WHERE a.adist IS NULL OR a.adist = '{{}}'::jsonb
                    GROUP BY a.company_id, a.account_id, p.default_analytic_id, a.dt
                ),

                all_rows AS (
                    SELECT * FROM dist_alloc
                    UNION ALL
                    SELECT * FROM nodist
                ),

                -- ============================================================
                -- 5) Consolidado diário por (company, account, analytic, dt)
                -- ============================================================
                summed AS (
                    SELECT
                        company_id,
                        account_id,
                        analytic_id,
                        dt,
                        SUM(debit)  AS debit,
                        SUM(credit) AS credit
                    FROM all_rows
                    GROUP BY company_id, account_id, analytic_id, dt
                ),

                -- ============================================================
                -- 6) (Opcional mas recomendado) “sementes” mensais (dia 01) para garantir continuidade
                --     Sem isso, o LAG pode “pular” meses sem movimento.
                -- ============================================================
                min_dates AS (
                    SELECT
                        company_id,
                        account_id,
                        analytic_id,
                        MIN(dt) AS min_dt
                    FROM summed
                    GROUP BY company_id, account_id, analytic_id
                ),
                month_zeros AS (
                    SELECT
                        m.company_id,
                        m.account_id,
                        m.analytic_id,
                        CAST(date_trunc('month', gs.dt) AS date) AS dt,
                        0::numeric AS debit,
                        0::numeric AS credit
                    FROM min_dates m
                    CROSS JOIN LATERAL generate_series(
                        m.min_dt,
                        current_date + 31,
                        interval '1 month'
                    ) AS gs(dt)
                ),
                summed2 AS (
                    SELECT
                        company_id,
                        account_id,
                        analytic_id,
                        dt,
                        SUM(debit)  AS debit,
                        SUM(credit) AS credit
                    FROM (
                        SELECT * FROM summed
                        UNION ALL
                        SELECT * FROM month_zeros
                    ) x
                    GROUP BY company_id, account_id, analytic_id, dt
                ),

                -- ============================================================
                -- 7) Saldos (running) e saldo anterior via LAG
                -- ============================================================
                balances AS (
                    SELECT
                        company_id   AS allss_company_id,
                        account_id   AS allss_account_id,
                        analytic_id  AS allss_account_analytic_id,
                        dt           AS allss_date,
                        debit        AS allss_debit,
                        credit       AS allss_credit,
                        SUM(debit - credit) OVER (
                            PARTITION BY company_id, account_id, analytic_id
                            ORDER BY dt, account_id
                        ) AS allss_final_balance
                    FROM summed2
                ),
                with_prev AS (
                    SELECT
                        b.*,
                        LAG(allss_final_balance, 1, 0) OVER (
                            PARTITION BY allss_company_id, allss_account_id, allss_account_analytic_id
                            ORDER BY allss_date, allss_account_id
                        ) AS allss_previous_balance
                    FROM balances b
                ),

                -- ============================================================
                -- 8) Enriquecimento com grupo/pais (MESMA base do Estruturado: ctb)
                -- ============================================================
                enrich AS (
                    SELECT
                        wp.allss_company_id,
                        wp.allss_account_id,
                        wp.allss_account_analytic_id,
                        aac.plan_id AS allss_analytic_plan_id,
                        wp.allss_date,
                        wp.allss_previous_balance,
                        wp.allss_debit,
                        wp.allss_credit,
                        wp.allss_final_balance,

                        ctb.group_id AS allss_group_id,

                        g3.parent_id AS allss_parent_id_3,
                        g4.parent_id AS allss_parent_id_4,
                        g5.parent_id AS allss_parent_id_5,
                        g6.parent_id AS allss_parent_id_6
                    FROM with_prev wp
                    LEFT JOIN account_analytic_account aac
                    ON aac.id = wp.allss_account_analytic_id

                    LEFT JOIN ctb
                    ON ctb.company_id = wp.allss_company_id
                    AND ctb.account_id = wp.allss_account_id

                    LEFT JOIN account_group g3 ON g3.id = ctb.group_id
                    LEFT JOIN account_group g4 ON g4.id = g3.parent_id
                    LEFT JOIN account_group g5 ON g5.id = g4.parent_id
                    LEFT JOIN account_group g6 ON g6.id = g5.parent_id
                )
                SELECT
                    1, NOW(), 1, NOW(),
                    e.allss_company_id,
                    e.allss_parent_id_6,
                    e.allss_parent_id_5,
                    e.allss_parent_id_4,
                    e.allss_parent_id_3,
                    e.allss_group_id,
                    e.allss_account_id,
                    e.allss_account_analytic_id,
                    e.allss_analytic_plan_id,
                    e.allss_date,
                    e.allss_previous_balance,
                    e.allss_debit,
                    e.allss_credit,
                    e.allss_final_balance
                FROM enrich e
                -- Segurança: não insere sem group_id (igual ao que você já fez no estruturado)
                WHERE e.allss_group_id IS NOT NULL
                ORDER BY e.allss_company_id, e.allss_account_id, e.allss_account_analytic_id, e.allss_date;
        """

        cr.execute(sql, (default_analytic_id,))

        if autocommit:
            cr.commit()



    def init_account_analytic(self, autocommit=False):
        """
        Insere linhas do dia 01 (mês atual) para todas as combinações
        (company, account, analytic) que ainda não possuem.
        Usa a própria tabela analítica como universo (rápido e coerente).
        """
        cr = self._cr

        cr.execute("SET LOCAL work_mem = '8MB'")
        cr.execute("SET LOCAL max_parallel_workers_per_gather = 0")
        cr.execute("SET LOCAL enable_hashagg = off")
        cr.execute("SET LOCAL enable_hashjoin = off")

        cr.execute("""
            WITH params AS (
                SELECT date_trunc('month', CURRENT_DATE)::date AS month_start
            ),

            targets AS (
                SELECT DISTINCT
                    a.allss_company_id          AS company_id,
                    a.allss_account_id          AS account_id,
                    a.allss_account_analytic_id AS analytic_id,
                    p.month_start               AS allss_date
                FROM allss_balance_account_analytic a
                CROSS JOIN params p
                WHERE a.allss_company_id IS NOT NULL
                AND a.allss_account_id IS NOT NULL
                AND a.allss_account_analytic_id IS NOT NULL
            ),

            missing AS (
                SELECT t.company_id, t.account_id, t.analytic_id, t.allss_date
                FROM targets t
                LEFT JOIN allss_balance_account_analytic cur
                ON cur.allss_company_id = t.company_id
                AND cur.allss_account_id = t.account_id
                AND cur.allss_account_analytic_id = t.analytic_id
                AND cur.allss_date = t.allss_date
                WHERE cur.id IS NULL
            )

            INSERT INTO allss_balance_account_analytic (
                create_uid, create_date, write_uid, write_date,
                allss_company_id,
                allss_parent_id_6,
                allss_parent_id_5,
                allss_parent_id_4,
                allss_parent_id_3,
                allss_group_id,
                allss_account_id,
                allss_account_analytic_id,
                allss_analytic_plan_id,
                allss_date,
                allss_previous_balance,
                allss_debit,
                allss_credit,
                allss_final_balance
            )
            SELECT
                1, NOW(), 1, NOW(),
                m.company_id,

                a_last.allss_parent_id_6,
                a_last.allss_parent_id_5,
                a_last.allss_parent_id_4,
                a_last.allss_parent_id_3,
                a_last.allss_group_id,

                m.account_id,
                m.analytic_id,

                a_last.allss_analytic_plan_id,  -- mantém o plano mais recente conhecido

                m.allss_date,

                COALESCE(prev.allss_final_balance, 0) AS allss_previous_balance,
                0::numeric AS allss_debit,
                0::numeric AS allss_credit,
                COALESCE(prev.allss_final_balance, 0) AS allss_final_balance

            FROM missing m

            -- último registro (qualquer data) para obter grupo/pais/plano
            LEFT JOIN LATERAL (
                SELECT
                    a2.allss_analytic_plan_id,
                    a2.allss_group_id,
                    a2.allss_parent_id_6,
                    a2.allss_parent_id_5,
                    a2.allss_parent_id_4,
                    a2.allss_parent_id_3
                FROM allss_balance_account_analytic a2
                WHERE a2.allss_company_id = m.company_id
                AND a2.allss_account_id = m.account_id
                AND a2.allss_account_analytic_id = m.analytic_id
                ORDER BY a2.allss_date DESC, a2.id DESC
                LIMIT 1
            ) a_last ON TRUE

            -- saldo anterior: último registro com data < mês atual (dia 01)
            LEFT JOIN LATERAL (
                SELECT a3.allss_final_balance
                FROM allss_balance_account_analytic a3
                WHERE a3.allss_company_id = m.company_id
                AND a3.allss_account_id = m.account_id
                AND a3.allss_account_analytic_id = m.analytic_id
                AND a3.allss_date < m.allss_date
                ORDER BY a3.allss_date DESC, a3.id DESC
                LIMIT 1
            ) prev ON TRUE

            -- segurança: se não houver estrutura/plano conhecidos, não insere “lixo”
            WHERE a_last.allss_group_id IS NOT NULL

            ON CONFLICT DO NOTHING;
        """)

        if autocommit:
            cr.commit()

        return True

