from odoo import api, models, fields, _

from datetime import date
from dateutil.relativedelta import relativedelta

import logging
_logger = logging.getLogger(__name__)


# FUNÇÃO PARA O CALCULO PARTIAL DOS SALDOS
def calculation_balances_partial_struc(self, data):
    result = self.env['allss.balance.account.structure'].search([
        ("allss_company_id", '=', data.get('allss_company_id', False)),
        ("allss_account_id", '=', data.get('allss_account_id', False)),],
        order='allss_company_id, allss_account_id, allss_date')

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
def update_account_init_struc(self, data):
    # UPDATE PARA A CONTA DO MÊS SEGUENTE
    _logger.warning(f"DATA update_account_init_struc {data}")
    year, month, day = str(data['allss_date']).split('-')
    now_date = date(int(year), int(month), int(day))
    now_date = now_date.replace(day=1)
    now_date = now_date + relativedelta(months=1)

    allss_account_move = self.env['allss.balance.account.structure']
    record_ids = allss_account_move.search([("allss_account_id", '=', data.get('allss_account_id', False)),
                                            ("allss_date", '=', now_date)])

    allss_account_id = data.get('allss_account_id')

    # SE O CADASTRO EXISTE ATUALIZA OS SALDOS
    if len(record_ids) > 0:
        for record in record_ids:
            if record.allss_debit == 0 and record.allss_credit == 0 and record.allss_account_id.id == allss_account_id:
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

        self.env['allss.balance.account.structure'].create(data)

    self.env.cr.commit()
    return

# Função para a modificação da tabela
# allss.balance.account.structure' as option:
# 1 -> CREATE 2 -> UPDATE 3 -> DELETE
def update_vals_structure(self, option, vals, data, res):

    # CREATE SE A CONTA NÃO EXISTE PARA A DATA ATUAL
    if option == 1:

        # PESQUISA DO CADASTRO INICIAL DA CONTA
        res = self.env['allss.balance.account.structure'].search([
        ("allss_company_id", '=', data.get('allss_company_id', False)),
        ("allss_account_id", '=', data.get('allss_account_id', False)),
        ], limit=1, order='allss_date desc, id desc')

        # CALCULO DO SALDO PREVIOUS E  FINAL
        data['allss_previous_balance'] = res.allss_final_balance
        data['allss_final_balance'] = res.allss_final_balance - data.get('allss_credit', 0) + data.get('allss_debit', 0)

        # CREATE DO CADASTRO DA CONTA COM A DATA ATUAL
        self.env['allss.balance.account.structure'].create(data)

    # UPDATE DA CONTA EXISTENTE
    elif option == 2:
        if data:
            # PROCURA O ID NA TABELA
            record_ids = self.env['allss.balance.account.structure'].search([('id', '=', data.get('id'))])

            for record in record_ids:
                # FAZ O CALCULOS DOS SALDOS
                allss_debit = record['allss_debit'] + data.get('allss_debit', 0)
                allss_credit = record['allss_credit'] + data.get('allss_credit', 0)
                allss_final_balance = record['allss_previous_balance'] - allss_credit + allss_debit
                data['allss_previous_balance'] = record['allss_previous_balance']
                data['allss_final_balance'] = allss_final_balance

                # EDIÇÃO DO CASDATRO EXISTENTE COM OS DADOS NOVOS
                record.write({
                    'allss_debit': allss_debit,
                    'allss_credit': allss_credit,
                    'allss_final_balance': allss_final_balance
                })

    # RESTA O VALOR DA CONTA EXISTENTE OU DELETA
    elif option == 3:
        #PROCURA O ID NA TABELA
        record_ids = self.env['allss.balance.account.structure'].search([('id', '=', res.id)])

        for record in record_ids:
            # PROCURA O DETALHE DA DATA DO CADASTRO
            year, month, day = str(record.allss_date).split('-')

            # CALCULO E ATUALIZAÇÃO DOS SALDOS
            allss_debit = record['allss_debit'] - vals.debit
            allss_credit = record['allss_credit'] - vals.credit
            allss_final_balance = record['allss_previous_balance'] + allss_credit - allss_debit
            data['allss_previous_balance'] = record['allss_previous_balance']
            data['allss_final_balance'] = allss_final_balance
            data['allss_date']= record.allss_date

            # Se debit e credit é zero (0) mais o dia é 01 ele deleta
            if allss_debit == 0 and allss_credit == 0 and day != '01':
                self.env['allss.balance.account.structure'].search([('id', '=', res.id)]).unlink()

            # Senão atualiza o cadastro que existe
            else:
                record.write({
                    'allss_debit': allss_debit,
                    'allss_credit': allss_credit,
                    'allss_final_balance': allss_final_balance
                })

    if option in [1, 2, 3]:

        # ATUALIZA O CADASTRO
        self.env.cr.commit()

        # ATUALIZAR O CRIAR A CONTA INICIAL
        update_account_init_struc(self, data)

        # CALCULO DOS SALDOS
        calculation_balances_partial_struc(self, data)

    return res


class AccountMoveLine(models.Model):
    _inherit = "account.move.line"

    allss_parent_id_6 = fields.Many2one(related='allss_parent_id_5.parent_id', string='1º Nível', store=True, index=True)
    allss_parent_id_5 = fields.Many2one(related='allss_parent_id_4.parent_id', string='2º Nível', store=True, index=True)
    allss_parent_id_4 = fields.Many2one(related='allss_parent_id_3.parent_id', string='3º Nível', store=True, index=True)
    allss_parent_id_3 = fields.Many2one(related='allss_group_id.parent_id', string='4º Nível', store=True, index=True)
    allss_group_id = fields.Many2one(related='account_id.group_id', string='5º Nível', store=True, index=True)


    # FUNÇÃO PARA O CALCULO GERAL DOS SALDOS
    def calculation_balances_general_struc(self):
        result = self.env['allss.balance.account.structure'].search([], order='allss_company_id,'
                                                                              'allss_account_id, '
                                                                              'allss_date')

        init = 0
        for res in result:

            if init != res.allss_account_id:
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

            init = res.allss_account_id

        return result


    def unlink(self):
        _logger.warning(f"🟢 >>>>>>> action_post do normal")
        res = None
        for move in self:
            if move.parent_state == 'posted':
                res_move = self.env['account.move'].search([('id', '=', move.move_id.id)])
                
                if res_move.state == 'draft':
                    continue                        
                result = self.env['allss.balance.account.structure'].search(["&",
                                                                    ('allss_account_id', '=', move.account_id.id),
                                                                    ("allss_date", "=", move.date),
                                                                    ("allss_company_id", "=", result.allss_company_id.id)
                                                                    ])
                
                # _logger.warning(f"RESULT unlink {result}")
                data = {
                    'allss_company_id': result.allss_company_id.id,
                    'allss_account_id': result.allss_account_id.id,
                    'allss_date': result.allss_date,
                    'allss_debit': result.allss_debit,
                    'allss_credit': result.allss_credit
                }
                update_vals_structure(self, 3, move, data, result)

            res = super(AccountMoveLine, self).unlink()
        return res


class AccountMoveStructure(models.Model):
    _inherit = 'account.move'

     
    # def post(self, invoice=False):
    def action_post(self):
        _logger.warning(f"🟢 >>>>>>> action_post do normal")
        res = super(AccountMoveStructure, self).action_post()

        for move in self:
            res_move_line = self.env['account.move.line'].search([('move_id', '=', move.id)])

            for move_line in res_move_line:

                result_ids = self.env['allss.balance.account.structure'].search(["&",
                                                                                 ('allss_account_id', '=', move_line.account_id.id),
                                                                                 ("allss_date", "=", move_line.date),
                                                                                 ("allss_company_id", "=", move_line.company_id.id)
                                                                                 ])
                _logger.warning(f"DENTRO DO POST RESULT IDS {result_ids}")

                data = {
                    'allss_company_id': move_line.company_id.id,
                    'allss_account_id': move_line.account_id.id,
                    'allss_date': move_line.date,
                    'allss_debit': move_line.debit,
                    'allss_credit': move_line.credit,
                    'allss_group_id': move_line.allss_group_id.id,
                    'allss_parent_id_3': move_line.allss_parent_id_3.id,
                    'allss_parent_id_4': move_line.allss_parent_id_4.id,
                    'allss_parent_id_5': move_line.allss_parent_id_5.id,
                    'allss_parent_id_6': move_line.allss_parent_id_6.id,
                }

                _logger.warning(f"DATA {data}")

                # SE A PESQUISA GERAR RESULTADO ATUALIZA O CADASTRO
                if len(result_ids) != 0:
                    for result in result_ids:
                        data.update({'id': result.id})
                        data.update({'allss_company_id': result.allss_company_id.id})
                        data.update({'allss_account_id': result.allss_account_id.id})
                        update_vals_structure(self, 2, None, data, res)

                # SE A PESQUISA NÃO GERAR RESULTADO CRIA O CADASTRO
                else:
                    update_vals_structure(self, 1, None, data, res)
        return res

    
    def cancel_register(self, res):
        for move in self:
            res_move_line = self.env['account.move.line'].search([('move_id', '=', move.id)])

            for move_line in res_move_line:

                result_ids = self.env['allss.balance.account.structure'].search(["&",
                                                                                 ('allss_account_id', '=', move_line.account_id.id),
                                                                                 ("allss_date", "=", move_line.date),
                                                                                 ("allss_company_id", "=", move_line.company_id.id)])

                data = {
                    'allss_company_id': move_line.company_id.id,
                    'allss_account_id': move_line.account_id.id,
                    'allss_date': move_line.date,
                    'allss_debit': -move_line.debit,
                    'allss_credit': -move_line.credit,
                    'allss_group_id': move_line.allss_group_id.id,
                    'allss_parent_id_3': move_line.allss_parent_id_3.id,
                    'allss_parent_id_4': move_line.allss_parent_id_4.id,
                    'allss_parent_id_5': move_line.allss_parent_id_5.id,
                    'allss_parent_id_6': move_line.allss_parent_id_6.id,
                }

                # SE A PESQUISA GERAR RESULTADO ATUALIZA O CADASTRO
                if len(result_ids) != 0:
                    _logger.warning(f"🔵Entrou no option com registros (Normal)")
                    for result in result_ids:
                        data.update({'id': result.id})
                        data.update({'allss_company_id': result.allss_company_id.id})
                        data.update({'allss_account_id': result.allss_account_id.id})
                        update_vals_structure(self, 2, None, data, res)

                # SE A PESQUISA NÃO GERAR RESULTADO CRIA O CADASTRO
                else:
                    _logger.warning(f"🔵Entrou no option sem registros (Normal)")
                    update_vals_structure(self, 1, None, data, res)
        return


    def button_cancel(self):
        if self.state == 'posted':
            self.cancel_register(self)
        res = super(AccountMoveStructure, self).button_cancel()
        return res

    def button_draft(self):
        if self.state == 'posted':
            self.cancel_register(self)
        res = super(AccountMoveStructure, self).button_draft()
        return res
