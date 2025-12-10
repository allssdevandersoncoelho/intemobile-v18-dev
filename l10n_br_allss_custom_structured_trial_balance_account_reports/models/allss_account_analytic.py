from odoo import api, models

from datetime import date
from dateutil.relativedelta import relativedelta
from .allss_funtions import account_analytic_def

import logging
_logger = logging.getLogger(__name__)


# FUNÇÃO PARA O CALCULO PARTIAL DOS SALDOS
def calculation_balances_partial(self, data):
    result = self.env['allss.balance.account.analytic'].search([
        ("allss_company_id", '=', data.get('allss_company_id', False)),
        ("allss_account_id", '=', data.get('allss_account_id', False)),
        ("allss_account_analytic_id", '=', data.get('allss_account_analytic_id', False)),],
        order='allss_company_id, allss_account_analytic_id, allss_account_id, allss_date')

    date_previous = None
    init = 0
    for res in result:

        if res.allss_date >= data['allss_date']:

            if init == 0:
                previous = res.allss_previous_balance
            else:
                previous = final

            if date_previous == res.allss_date:
                allss_credit = res.allss_credit + allss_credit
                allss_debit = res.allss_debit + allss_debit
            else:
                allss_credit = res.allss_credit
                allss_debit = res.allss_debit

            final = previous - allss_credit + allss_debit

            res.write({
                'allss_previous_balance': previous,
                'allss_credit': allss_credit,
                'allss_debit': allss_debit,
                'allss_final_balance': final
            })
            self.env.cr.commit()
            init = init + 1

        date_previous = res.allss_date
    return result


# FUNÇÃO PARA CREATE O UPDATE DA CONTA INICIAL DO MÊS SEGUENTE
def update_account_init(self, data):
    # UPDATE PARA A CONTA DO MÊS SEGUENTE
    _logger.warning(f'DATA update_account_init: {data}')
    year, month, day = str(data['allss_date']).split('-')
    now_date = date(int(year), int(month), int(day))
    now_date = now_date.replace(day=1)
    now_date = now_date + relativedelta(months=1)

    allss_account_move = self.env['allss.balance.account.analytic']
    record_ids = allss_account_move.search([("allss_account_id", '=', data.get('allss_account_id', False)),
                                            ("allss_account_analytic_id", '=', data.get('allss_account_analytic_id', False)),
                                            ("allss_date", '=', now_date)])

    allss_account_analytic = data.get('allss_account_analytic_id')

    # SE O CADASTRO EXISTE ATUALIZA OS SALDOS
    if len(record_ids) > 0:
        for record in record_ids:
            if record.allss_debit == 0 and record.allss_credit == 0 and record.allss_account_analytic_id.id == allss_account_analytic:
                record.write({
                    'allss_previous_balance': data.get('allss_final_balance', None),
                    'allss_final_balance': data.get('allss_final_balance', None)
                })

    # SE O CADASTRO NÃO EXISTE CRIA O NOVO CADASTRO
    elif len(record_ids) == 0:
        data.update({'allss_date': now_date})
        data.update({'allss_previous_balance': data.get('allss_final_balance', 0)})
        data.update({'allss_credit': 0.0})
        data.update({'allss_debit': 0.0})
        data.update({'allss_final_balance': data.get('allss_final_balance', 0)})
        self.env['allss.balance.account.analytic'].create(data)

    self.env.cr.commit()
    return

# Função para a modificação da tabela
# allss.balance.account.analytic' as option:
# 1 -> CREATE 2 -> UPDATE 3 -> DELETE
def update_vals(self, option, vals, data, res):

    # CREATE SE A CONTA NÃO EXISTE PARA A DATA ATUAL
    if option == 1:

        # PESQUISA DO CADASTRO INICIAL DA CONTA
        res = self.env['allss.balance.account.analytic'].search([
        ("allss_company_id", '=', data.get('allss_company_id', False)),
        ("allss_account_id", '=', data.get('allss_account_id', False)),
        ("allss_account_analytic_id", '=', data.get('allss_account_analytic_id', False)),
        ], limit=1, order='allss_date desc, id desc')

        # CALCULO DO SALDO PREVIOUS E  FINAL
        data['allss_previous_balance'] = res.allss_final_balance
        data['allss_final_balance'] = res.allss_final_balance - data.get('allss_credit', 0) + data.get('allss_debit', 0)

        # CREATE DO CADASTRO DA CONTA COM A DATA ATUAL
        self.env['allss.balance.account.analytic'].create(data)

    # UPDATE DA CONTA EXISTENTE
    elif option == 2:
        if data:
            # PROCURA O ID NA TABELA
            record_ids = self.env['allss.balance.account.analytic'].search([('id', '=', data.get('id'))])

            for record in record_ids:
                # FAZ O CALCULOS DOS SALDOS
                allss_debit = record['allss_debit'] + data.get('allss_debit', 0)
                allss_credit = record['allss_credit'] + data.get('allss_credit', 0)
                allss_final_balance = record['allss_previous_balance'] - allss_credit + allss_debit
                data['allss_previous_balance'] = record['allss_previous_balance']
                data['allss_final_balance'] = allss_final_balance

                # EDIÇÃO DO CASDATRO EXISTENTE COM OS DADOS NOVOS
                record.write({
                    'allss_analytic_plan_id': data['allss_analytic_plan_id'],
                    'allss_account_analytic_id': data['allss_account_analytic_id'],
                    'allss_debit': allss_debit,
                    'allss_credit': allss_credit,
                    'allss_final_balance': allss_final_balance})

    # RESTA O VALOR DA CONTA EXISTENTE OU DELETA
    elif option == 3:
        #PROCURA O ID NA TABELA
        record_ids = self.env['allss.balance.account.analytic'].search([('id', '=', res.id)])

        for record in record_ids:
            # PROCURA O DETALHE DA DATA DO CADASTRO
            year, month, day = str(record.allss_date).split('-')

            # CALCULO E ATUALIZAÇÃO DOS SALDOS
            allss_debit = record['allss_debit'] - vals.debit
            allss_credit = record['allss_credit'] - vals.credit
            allss_final_balance = record['allss_previous_balance'] + allss_credit - allss_debit
            data['allss_previous_balance'] = record['allss_previous_balance']
            data['allss_final_balance'] = allss_final_balance
            data['allss_date'] = record.allss_date

            # Se debit e credit é zero (0) mais o dia não é 01 ele deleta
            if allss_debit == 0 and allss_credit == 0 and day != '01':
                self.env['allss.balance.account.analytic'].search([('id', '=', res.id )]).unlink()

            # Senão atualiza o cadastro que existe
            else:
                record.write({
                    'allss_analytic_plan_id': data['allss_analytic_plan_id'],
                    'allss_account_analytic_id': data['allss_account_analytic_id'],
                    'allss_debit': allss_debit,
                    'allss_credit': allss_credit,
                    'allss_final_balance': allss_final_balance
                })

    if option in [1, 2, 3]:

        # ATUALIZA O CADASTRO
        self.env.cr.commit()

        # ATUALIZAR O CRIAR A CONTA INICIAL
        update_account_init(self, data)

        # CALCULO DOS SALDOS
        calculation_balances_partial(self, data)

    return res


class AccountAnalytic(models.Model):
    _inherit = "account.move.line"

    # FUNÇÃO PARA O CALCULO GERAL DOS SALDOS
     
    def calculation_balances_general(self):
        result = self.env['allss.balance.account.analytic'].search([], order='allss_company_id, '
                                                                             'allss_analytic_plan_id,'
                                                                             'allss_account_analytic_id, '
                                                                             'allss_account_id, allss_date')

        account_init = 0
        account_analytic_init = 0

        for res in result:

            if account_init != res.allss_account_id or account_analytic_init != res.allss_account_analytic_id:
                allss_credit = res.allss_credit
                allss_debit = res.allss_debit
                previous = 0
            else:
                allss_credit = res.allss_credit
                allss_debit = res.allss_debit
                previous = final

            final = previous + allss_debit - allss_credit

            res.write({
                'allss_previous_balance': previous,
                'allss_credit': allss_credit,
                'allss_debit': allss_debit,
                'allss_final_balance': final
            })

            account_init = res.allss_account_id
            account_analytic_init = res.allss_account_analytic_id

        return result

     
    def unlink(self):
        for move in self:
            res_move = self.env['account.move'].search([('id', '=', move.move_id.id)])

            if res_move.state == 'draft':
                return

            if move.analytic_distribution:
        
                analytic_ids = [int(x) for x in move.analytic_distribution.keys()]

                result = self.env['allss.balance.account.analytic'].search(["&",
                                                                    ('allss_account_id', '=', move.account_id.id),
                                                                    ("allss_account_analytic_id", "in", analytic_ids),
                                                                    ("allss_date", "=", move.date)])
                _logger.warning(f"🟢 Result {result} | analytic_account_id {analytic_ids}")

                for line in result:
                    data = {
                        'allss_company_id': line.allss_company_id.id,
                        'allss_account_id': line.allss_account_id.id,
                        'allss_analytic_plan_id': line.allss_analytic_plan_id.id,
                        'allss_account_analytic_id': line.allss_account_analytic_id.id,
                        'allss_date': line.allss_date,
                        'allss_debit': line.allss_debit,
                        'allss_credit': line.allss_credit
                    }

                    update_vals(self, 3, move, data, line)

        res = super(AccountAnalytic, self).unlink()
        return res


class AccountMoveAnalytic(models.Model):
    _inherit = 'account.move'

     
    def action_post(self):
        res = super(AccountMoveAnalytic, self).action_post()

        for move in self:
            res_move_line = self.env['account.move.line'].search([('move_id', '=', move.id)])

            for move_line in res_move_line:
                analytic_distribution = move_line.analytic_distribution.keys() if move_line.analytic_distribution else False

                if not analytic_distribution:
                    analytic_ids = [account_analytic_def(move_line)[0]]
                    analytic_account_plan_id = account_analytic_def(move_line)[1]
                else:
                    analytic_ids = [int(x) for x in analytic_distribution]
                    analytic_account_plan_id = self.env['account.analytic.account']. \
                        search([('id', 'in', analytic_ids)]).plan_id.id
                    
                for analytic_account_id in analytic_ids:                
                    result_ids = self.env['allss.balance.account.analytic'].search(["&",
                                                                                    ('allss_account_id', '=',
                                                                                    move_line.account_id.id),
                                                                                    ("allss_account_analytic_id", "=",
                                                                                    analytic_account_id),
                                                                                    ("allss_date", "=", move_line.date)])
                    data = {
                        'allss_company_id': move_line.company_id.id,
                        'allss_account_id': move_line.account_id.id,
                        'allss_account_analytic_id': analytic_account_id,
                        'allss_analytic_plan_id': analytic_account_plan_id,
                        'allss_date': move_line.date,
                        'allss_debit': move_line.debit,
                        'allss_credit': move_line.credit,
                        'allss_group_id': move_line._allss_group_id.id,
                        'allss_parent_id_3': move_line._allss_parent_id_3.id,
                        'allss_parent_id_4': move_line._allss_parent_id_4.id,
                        'allss_parent_id_5': move_line._allss_parent_id_5.id,
                        'allss_parent_id_6': move_line._allss_parent_id_6.id,
                    }

                    # SE A PESQUISA GERAR RESULTADO ATUALIZA O CADASTRO
                    if len(result_ids) != 0:
                        for result in result_ids:
                            data.update({'id': result.id})
                            data.update({'allss_analytic_plan_id': result.allss_analytic_plan_id.id})
                            data.update({'allss_company_id': result.allss_company_id.id})
                            data.update({'allss_account_id': result.allss_account_id.id})
                            data.update({'allss_account_analytic_id': result.allss_account_analytic_id.id})
                            update_vals(self, 2, None, data, res)

                    # SE A PESQUISA NÃO GERAR RESULTADO CRIA O CADASTRO
                    else:
                        update_vals(self, 1, None, data, res)
        return res

    def button_cancel(self):
        res = super(AccountMoveAnalytic, self).button_cancel()
        for move in self:
            res_move_line = self.env['account.move.line'].search([('move_id', '=', move.id)])

            for move_line in res_move_line:
                analytic_distribution = move_line.analytic_distribution.keys() if move_line.analytic_distribution else False

                if not analytic_distribution:
                    # analytic_account_id = account_analytic_def(move_line)[0]
                    analytic_ids = [account_analytic_def(move_line)[0]]
                    analytic_account_plan_id = account_analytic_def(move_line)[1]
                else:
                    analytic_ids = [int(x) for x in analytic_distribution]
                    analytic_account_plan_id = self.env['account.analytic.account']. \
                        search([('id', '=', analytic_ids)]).plan_id.id

                for analytic_account_id in analytic_ids:  
                    result_ids = self.env['allss.balance.account.analytic'].search(["&",
                                                                                    ('allss_account_id', '=',
                                                                                    move_line.account_id.id),
                                                                                    ("allss_account_analytic_id", "=",
                                                                                    analytic_account_id),
                                                                                    ("allss_date", "=", move_line.date)])

                    data = {
                        'allss_company_id': move_line.company_id.id,
                        'allss_account_id': move_line.account_id.id,
                        'allss_account_analytic_id': analytic_account_id,
                        'allss_analytic_plan_id': analytic_account_plan_id,
                        'allss_date': move_line.date,
                        'allss_debit': -move_line.debit,
                        'allss_credit': -move_line.credit,
                        'allss_group_id': move_line._allss_group_id.id,
                        'allss_parent_id_3': move_line._allss_parent_id_3.id,
                        'allss_parent_id_4': move_line._allss_parent_id_4.id,
                        'allss_parent_id_5': move_line._allss_parent_id_5.id,
                        'allss_parent_id_6': move_line._allss_parent_id_6.id,
                    }

                    # SE A PESQUISA GERAR RESULTADO ATUALIZA O CADASTRO
                    if len(result_ids) != 0:
                        for result in result_ids:
                            data.update({'id': result.id})
                            data.update({'allss_analytic_plan_id': result.allss_analytic_plan_id.id})
                            data.update({'allss_company_id': result.allss_company_id.id})
                            data.update({'allss_account_id': result.allss_account_id.id})
                            data.update({'allss_account_analytic_id': result.allss_account_analytic_id.id})
                            update_vals(self, 2, None, data, res)

                    # SE A PESQUISA NÃO GERAR RESULTADO CRIA O CADASTRO
                    else:
                        update_vals(self, 1, None, data, res)

        return res