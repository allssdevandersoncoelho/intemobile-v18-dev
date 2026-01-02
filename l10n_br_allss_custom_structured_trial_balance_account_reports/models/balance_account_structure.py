import re
import logging
from odoo import fields, models, api, _     #, tools
# import odoo.addons.decimal_precision as dp
# from datetime import date

_logger = logging.getLogger(__name__)

# Date Mask
bdate = re.compile(r'\d{4}\-\d{2}\-\d{2}')

# Domain operators.
NOT_OPERATOR = '!'
OR_OPERATOR = '|'
AND_OPERATOR = '&'
DOMAIN_OPERATORS = (NOT_OPERATOR, OR_OPERATOR, AND_OPERATOR)

# List of available term operators. It is also possible to use the '<>'
# operator, which is strictly the same as '!='; the later should be prefered
# for consistency. This list doesn't contain '<>' as it is simpified to '!='
# by the normalize_operator() function (so later part of the code deals with
# only one representation).
# Internals (i.e. not available to the user) 'inselect' and 'not inselect'
# operators are also used. In this case its right operand has the form (subselect, params).
TERM_OPERATORS = ('=', '!=', '<=', '<', '>', '>=', '=?', '=like', '=ilike',
                  'like', 'not like', 'ilike', 'not ilike', 'in', 'not in',
                  'child_of', 'parent_of')

# A subset of the above operators, with a 'negative' semantic. When the
# expressions 'in NEGATIVE_TERM_OPERATORS' or 'not in NEGATIVE_TERM_OPERATORS' are used in the code
# below, this doesn't necessarily mean that any of those NEGATIVE_TERM_OPERATORS is
# legal in the processed term.
NEGATIVE_TERM_OPERATORS = ('!=', 'not like', 'not ilike', 'not in')

# Negation of domain expressions
DOMAIN_OPERATORS_NEGATION = {
    AND_OPERATOR: OR_OPERATOR,
    OR_OPERATOR: AND_OPERATOR,
}
TERM_OPERATORS_NEGATION = {
    '<': '>=',
    '>': '<=',
    '<=': '>',
    '>=': '<',
    '=': '!=',
    '!=': '=',
    'in': 'not in',
    'like': 'not like',
    'ilike': 'not ilike',
    'not in': 'in',
    'not like': 'like',
    'not ilike': 'ilike',
}

TRUE_LEAF = (1, '=', 1)
FALSE_LEAF = (0, '=', 1)

TRUE_DOMAIN = [TRUE_LEAF]
FALSE_DOMAIN = [FALSE_LEAF]


class BalanceAccountStructure(models.Model):
    _name = "allss.balance.account.structure"
    _description = "Balancete Estruturado"
    _order = "allss_company_id, allss_account_id, allss_date"

    allss_company_id = fields.Many2one('res.company', string='Empresa', store=True, index=True)

    allss_parent_id_6 = fields.Many2one('account.group', string='1º Nível', store=True, index=True)
    allss_parent_id_5 = fields.Many2one('account.group', string='2º Nível', store=True, index=True)
    allss_parent_id_4 = fields.Many2one('account.group', string='3º Nível', store=True, index=True)
    allss_parent_id_3 = fields.Many2one('account.group', string='4º Nível', store=True, index=True)
    allss_group_id = fields.Many2one('account.group', string='5º Nível', store=True, index=True)

    allss_account_id = fields.Many2one('account.account', string='Conta', store=True, index=True)

    allss_date = fields.Date("Data", store=True, index=True)

    allss_previous_balance = fields.Float("Saldo Anterior", store=True, index=True, digits='Account Balance')
    allss_debit = fields.Float("Débito", store=True, index=True, digits='Account Balance')
    allss_credit = fields.Float("Crédito", store=True, index=True, digits='Account Balance')
    allss_final_balance = fields.Float("Saldo Atual", store=True, index=True, digits='Account Balance')

    
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

        table = self._table  # "allss_balance_account_structure"

        for group_line in result:
            gdom = group_line.get('__domain')
            if not gdom:
                continue

            cnt = group_line.get('allss_account_id_count')
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
                    SELECT DISTINCT ON ("{table}"."allss_company_id", "{table}"."allss_account_id")
                        "{table}"."allss_company_id",
                        "{table}"."allss_account_id",
                        "{table}"."allss_previous_balance" AS prev
                    FROM {from_code}
                    {where_sql}
                    ORDER BY
                        "{table}"."allss_company_id",
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



    def open_document(self, options=None, params=None):
        domain = ['&',
                  ('date', '=', self.allss_date),
                  ('account_id', '=', self.allss_account_id.id),
                  ('parent_state', '=', 'posted')
                  ]
        dict_ret = {'type': 'ir.actions.act_window',
                    'name': f'Balancete Estruturado - Conta: {self.allss_account_id.id} - Data: {self.allss_date}',
                    'res_model': 'account.move.line',
                    # 'view_type': 'list',
                    'view_mode': 'list,pivot,kanban,graph,form',
                    'domain': domain
                    }
        return dict_ret


    
    def init_account_structure(self, autocommit=False):
        """ Insere linhas do dia 01 para todas as contas/empresas que ainda não possuem. """
        cr = self._cr

        cr.execute("SET LOCAL work_mem = '8MB'")
        cr.execute("SET LOCAL max_parallel_workers_per_gather = 0")
        cr.execute("SET LOCAL enable_hashagg = off")
        cr.execute("SET LOCAL enable_hashjoin = off")

        cr.execute("""
            WITH params AS (
                SELECT date_trunc('month', CURRENT_DATE)::date AS month_start
            ),

            -- Universo de contas/empresas que devem ter “linha do dia 01”
            -- Aqui eu uso a própria tabela estruturada (mais coerente e rápido),
            -- pois ela já carrega company/account e grupo/pais.
            targets AS (
                SELECT DISTINCT
                    s.allss_company_id AS company_id,
                    s.allss_account_id AS account_id,
                    p.month_start      AS allss_date
                FROM allss_balance_account_structure s
                CROSS JOIN params p
            ),

            missing AS (
                SELECT t.company_id, t.account_id, t.allss_date
                FROM targets t
                LEFT JOIN allss_balance_account_structure cur
                ON cur.allss_company_id = t.company_id
                AND cur.allss_account_id = t.account_id
                AND cur.allss_date = t.allss_date
                WHERE cur.id IS NULL
            )

            INSERT INTO allss_balance_account_structure (
                create_uid, create_date, write_uid, write_date,
                allss_company_id,
                allss_parent_id_6,
                allss_parent_id_5,
                allss_parent_id_4,
                allss_parent_id_3,
                allss_group_id,
                allss_account_id,
                allss_date,
                allss_previous_balance,
                allss_debit,
                allss_credit,
                allss_final_balance
            )
            SELECT
                1, NOW(), 1, NOW(),
                m.company_id,

                -- estrutura (grupo/pais): pega do “último registro conhecido”
                s_last.allss_parent_id_6,
                s_last.allss_parent_id_5,
                s_last.allss_parent_id_4,
                s_last.allss_parent_id_3,
                s_last.allss_group_id,

                m.account_id,
                m.allss_date,

                COALESCE(prev.allss_final_balance, 0) AS allss_previous_balance,
                0::numeric AS allss_debit,
                0::numeric AS allss_credit,
                COALESCE(prev.allss_final_balance, 0) AS allss_final_balance

            FROM missing m

            -- último registro (qualquer data) para obter grupo e pais
            LEFT JOIN LATERAL (
                SELECT
                    s2.allss_group_id,
                    s2.allss_parent_id_6,
                    s2.allss_parent_id_5,
                    s2.allss_parent_id_4,
                    s2.allss_parent_id_3
                FROM allss_balance_account_structure s2
                WHERE s2.allss_company_id = m.company_id
                AND s2.allss_account_id = m.account_id
                ORDER BY s2.allss_date DESC, s2.id DESC
                LIMIT 1
            ) s_last ON TRUE

            -- saldo anterior: último registro com data < mês atual (dia 01)
            LEFT JOIN LATERAL (
                SELECT s3.allss_final_balance
                FROM allss_balance_account_structure s3
                WHERE s3.allss_company_id = m.company_id
                AND s3.allss_account_id = m.account_id
                AND s3.allss_date < m.allss_date
                ORDER BY s3.allss_date DESC, s3.id DESC
                LIMIT 1
            ) prev ON TRUE

            -- segurança: se por algum motivo não houver estrutura (s_last NULL), não insere “lixo”
            WHERE s_last.allss_group_id IS NOT NULL

            -- concorrência/idempotência (requer o índice único parcial ou UNIQUE correspondente)
            ON CONFLICT DO NOTHING;
        """)

        if autocommit:
            cr.commit()

        return True



    def execute_sql(self, autocommit=False):
        """ Recria toda a tabela de saldos estruturados. CUIDADO: apaga tudo antes. """
        cr = self._cr

        cr.execute("SET LOCAL work_mem = '8MB'")
        cr.execute("SET LOCAL max_parallel_workers_per_gather = 0")
        cr.execute("SET LOCAL enable_hashagg = off")
        cr.execute("SET LOCAL enable_hashjoin = off")

        cr.execute("TRUNCATE TABLE allss_balance_account_structure RESTART IDENTITY CASCADE;")

        cr.execute("""
            INSERT INTO allss_balance_account_structure (
                create_uid, create_date, write_uid, write_date,
                allss_company_id,
                allss_parent_id_6,
                allss_parent_id_5,
                allss_parent_id_4,
                allss_parent_id_3,
                allss_group_id,
                allss_account_id,
                allss_date,
                allss_previous_balance,
                allss_debit,
                allss_credit,
                allss_final_balance
            )
            WITH ctb AS (
                SELECT
                    g.company_id        AS company_id,
                    g.id                AS group_id,
                    c.id                AS account_id
                FROM account_account c
                CROSS JOIN LATERAL jsonb_each_text(COALESCE(c.code_store, '{}'::jsonb)) AS j(key, value)
                JOIN LATERAL (
                    SELECT g.*
                    FROM account_group g
                    WHERE g.company_id::text = j.key
                    AND LEFT(j.value, LENGTH(g.code_prefix_start)) = g.code_prefix_start
                    ORDER BY LENGTH(g.code_prefix_start) DESC
                    LIMIT 1
                ) g ON TRUE
            ),
            mv_atu AS (
                SELECT
                    company_id,
                    account_id,
                    date,
                    SUM(debit)  AS debit,
                    SUM(credit) AS credit
                FROM (
                    SELECT
                        mov.company_id,
                        mov.account_id,
                        CAST(date_trunc('month', gs.dt) AS date) AS date,
                        0::numeric AS debit,
                        0::numeric AS credit
                    FROM (
                        SELECT company_id, account_id, MIN(date) AS min_date
                        FROM account_move_line
                        GROUP BY company_id, account_id
                    ) mov
                    CROSS JOIN LATERAL generate_series(
                        mov.min_date,
                        current_date + 31,
                        interval '1 month'
                    ) AS gs(dt)

                    UNION ALL

                    SELECT
                        aml.company_id,
                        aml.account_id,
                        aml.date,
                        aml.debit,
                        aml.credit
                    FROM account_move_line aml
                    JOIN account_move am
                    ON am.id = aml.move_id
                    AND am.state = 'posted'
                ) cons
                GROUP BY company_id, account_id, date
            ),
            base AS (
                SELECT
                    ctb.company_id                      AS allss_company_id,
                    ctb.group_id                        AS allss_group_id,
                    ctb.account_id                      AS allss_account_id,
                    COALESCE(mv_atu.date, CURRENT_DATE) AS allss_date,
                    COALESCE(mv_atu.debit, 0)           AS allss_debit,
                    COALESCE(mv_atu.credit, 0)          AS allss_credit,
                    COALESCE(
                        SUM(COALESCE(mv_atu.debit,0) - COALESCE(mv_atu.credit,0)) OVER (
                            PARTITION BY ctb.company_id, ctb.group_id, ctb.account_id
                            ORDER BY ctb.company_id, ctb.group_id, ctb.account_id, mv_atu.date
                        ),
                        0
                    ) AS allss_final_balance
                FROM ctb
                LEFT JOIN mv_atu
                ON mv_atu.company_id = ctb.company_id
                AND mv_atu.account_id = ctb.account_id
            ),
            grp AS (
                SELECT
                    b.*,
                    (b.allss_final_balance + b.allss_credit - b.allss_debit) AS allss_previous_balance,

                    g3.parent_id AS allss_parent_id_3,
                    g4.parent_id AS allss_parent_id_4,
                    g5.parent_id AS allss_parent_id_5,
                    g6.parent_id AS allss_parent_id_6
                FROM base b
                LEFT JOIN account_group g3 ON g3.id = b.allss_group_id
                LEFT JOIN account_group g4 ON g4.id = g3.parent_id
                LEFT JOIN account_group g5 ON g5.id = g4.parent_id
                LEFT JOIN account_group g6 ON g6.id = g5.parent_id
            )
            SELECT
                1    AS create_uid,
                NOW() AS create_date,
                1    AS write_uid,
                NOW() AS write_date,
                allss_company_id,
                allss_parent_id_6,
                allss_parent_id_5,
                allss_parent_id_4,
                allss_parent_id_3,
                allss_group_id,
                allss_account_id,
                allss_date,
                allss_previous_balance,
                allss_debit,
                allss_credit,
                allss_final_balance
            FROM grp
            -- WHERE allss_account_id = 3527  -- somente para teste
            ORDER BY allss_company_id, allss_account_id, allss_date
        """)

        # Um único commit no final, se você realmente precisa controlar commit aqui.
        if autocommit:
            cr.commit()



    def _ensure_allss_indexes_for_balancete(self, concurrently=True):
        """Garante que os índices necessários para o balancete estruturado estejam criados."""
        cr = self._cr
        suffix = " CONCURRENTLY" if concurrently else ""

        statements = [
            # ============================================================
            # 1) INTEGRIDADE / CONCORRÊNCIA
            #    Garante 1 registro no dia 01 por (company, account, date).
            #    Permite múltiplos registros em outros dias do mês.
            # ============================================================
            f"""
            CREATE UNIQUE INDEX{suffix} IF NOT EXISTS l10n_br_allss_bal_struct_uniq_m01
            ON allss_balance_account_structure (allss_company_id, allss_account_id, allss_date)
            WHERE EXTRACT(day FROM allss_date) = 1;
            """,

            # ============================================================
            # 2) PERFORMANCE - allss_balance_account_structure
            #    (a) Para "pegar último registro" por company/account:
            #        usado em LATERAL (saldo anterior / último saldo).
            # ============================================================
            f"""
            CREATE INDEX{suffix} IF NOT EXISTS l10n_br_allss_bal_struct_company_account_date_desc
            ON allss_balance_account_structure (allss_company_id, allss_account_id, allss_date DESC, id DESC);
            """,

            #    (b) Para "pegar primeiro registro" por company/account:
            #        usado no read_group com DISTINCT ON / ORDER BY date,id ASC.
            f"""
            CREATE INDEX{suffix} IF NOT EXISTS l10n_br_allss_bal_struct_company_account_date_id
            ON allss_balance_account_structure (allss_company_id, allss_account_id, allss_date, id);
            """,

            #    (c) Opcional, mas útil se você filtra muito por data no domínio
            #        (por exemplo, balancete por período). Ajuda a reduzir scan.
            f"""
            CREATE INDEX{suffix} IF NOT EXISTS l10n_br_allss_bal_struct_date
            ON allss_balance_account_structure (allss_date);
            """,

            #    (d) Opcional, útil se domínios filtram por hierarquia/grupos.
            #        (ex.: allss_parent_id_6 = X, allss_group_id = Y)
            f"""
            CREATE INDEX{suffix} IF NOT EXISTS l10n_br_allss_bal_struct_parent6
            ON allss_balance_account_structure (allss_parent_id_6);
            """,
            f"""
            CREATE INDEX{suffix} IF NOT EXISTS l10n_br_allss_bal_struct_parent5
            ON allss_balance_account_structure (allss_parent_id_5);
            """,
            f"""
            CREATE INDEX{suffix} IF NOT EXISTS l10n_br_allss_bal_struct_parent4
            ON allss_balance_account_structure (allss_parent_id_4);
            """,
            f"""
            CREATE INDEX{suffix} IF NOT EXISTS l10n_br_allss_bal_struct_parent3
            ON allss_balance_account_structure (allss_parent_id_3);
            """,
            f"""
            CREATE INDEX{suffix} IF NOT EXISTS l10n_br_allss_bal_struct_group
            ON allss_balance_account_structure (allss_group_id);
            """,

            # ============================================================
            # 3) PERFORMANCE - account_move_line / account_move
            #    Usado no execute_sql (mv_atu / min(date) / joins / filtros posted).
            # ============================================================
            f"""
            CREATE INDEX{suffix} IF NOT EXISTS l10n_br_allss_aml_company_account_date
            ON account_move_line (company_id, account_id, date);
            """,
            f"""
            CREATE INDEX{suffix} IF NOT EXISTS l10n_br_allss_aml_move_id
            ON account_move_line (move_id);
            """,
            f"""
            CREATE INDEX{suffix} IF NOT EXISTS l10n_br_allss_am_state_id
            ON account_move (state, id);
            """,

            # ============================================================
            # 4) PERFORMANCE - account_group
            #    Usado no match de prefixo (ctb) e seleção do prefixo mais longo.
            # ============================================================
            f"""
            CREATE INDEX{suffix} IF NOT EXISTS l10n_br_allss_ag_company_prefix
            ON account_group (company_id, code_prefix_start);
            """,
        ]

        for sql in statements:
            cr.execute(sql)


    def ensure_indexes_then_recalc(self, index_creation_mode=False, fallback_non_concurrently=False):
        cr = self._cr

        # Evita concorrência
        cr.execute("SELECT pg_advisory_lock(hashtext('allss_balance_account_structure_recalc'));")
        try:
            if index_creation_mode:
                # CREATE INDEX CONCURRENTLY exige fora de transação
                cr.commit()
                try:
                    self._ensure_allss_indexes_for_balancete(concurrently=True)
                    cr.commit()
                except Exception:
                    cr.rollback()
                    if fallback_non_concurrently:
                        _logger.warning("Fallback sem CONCURRENTLY habilitado; pode bloquear escrita.")
                        self._ensure_allss_indexes_for_balancete(concurrently=False)
                        cr.commit()
                    else:
                        raise

            # Rodar em uma transação única (tudo ou nada)
            with cr.savepoint():
                self.execute_sql(autocommit=False)
                self.init_account_structure(autocommit=False)

            cr.commit()

        except Exception:
            cr.rollback()
            raise

        finally:
            try:
                cr.execute("SELECT pg_advisory_unlock(hashtext('allss_balance_account_structure_recalc'));")
            except Exception:
                _logger.exception("Falha ao liberar advisory lock.")
 

  

    def update_balance(self):
        for rec in self:
            _logger.warning(f'####################### ATUALIZAR SALDOS #######################')
            rec.env.ref('l10n_br_allss_custom_structured_trial_balance_account_reports.balance_structure_update_data').method_direct_trigger()
            break
