# -*- coding: utf-8 -*-
# © 2025 ALLSS Soluções em Sistemas LTDA
# License AGPL-3.0 or later (http://www.gnu.org/licenses/agpl.html)

import base64
import logging

_logger = logging.getLogger(__file__)

# from os import path
# from zipfile import ZipFile
# from io import BytesIO
from lxml import objectify
from lxml.etree import XMLSyntaxError

from odoo import models, fields
from odoo.exceptions import UserError, RedirectWarning, ValidationError

class L10nBrAlssWizardNfeImport(models.TransientModel):
    _inherit = 'l10n.br.allss.wizard.nfe.import'

    def default_l10n_br_allss_picking_type_id(self):
        l10n_br_allss_picking_type_id = self.env['stock.picking.type'].sudo().with_company(self.company_id).search([
            ('code', '=', 'outgoing'),
            ('company_id', 'in', [self.company_id.id, False])
        ], limit=1)
        return l10n_br_allss_picking_type_id.id if l10n_br_allss_picking_type_id else None

    l10n_br_allss_group_id = fields.Many2one('account.group', 'Grupo Contábil')
    l10n_br_allss_picking_type_id = fields.Many2one('stock.picking.type', 
                                                    string='Tipo de Operação'
                                                    # default=default_l10n_br_allss_picking_type_id,
                                                    # domain="[('company_id', '=', company_id)]"
                                                    )
    
    l10n_br_allss_journal_id = fields.Many2one('account.journal', 'Diário')
    l10n_br_allss_account_analytic_id = fields.Many2one('account.analytic.account', 'Conta Analítica')
    l10n_br_allss_account_account_id = fields.Many2one('account.account', 'Conta Contábil (Fatura)')




    def _l10n_br_allss_import_xml_out_invoice(self, auto, xml):
        nfe = objectify.fromstring(xml)
        obj_account_move = self.env['account.move'].sudo().with_context(l10n_br_allss_group_id=self.l10n_br_allss_group_id,
                                                                        l10n_br_allss_picking_type_id=self.l10n_br_allss_picking_type_id,
                                                                        l10n_br_allss_journal_id=self.l10n_br_allss_journal_id,
                                                                        l10n_br_allss_account_analytic_id=self.l10n_br_allss_account_analytic_id,
                                                                        l10n_br_allss_account_account_id=self.l10n_br_allss_account_account_id
                                                                        ).sudo()
        company_id = self.env.company.sudo()

        move = obj_account_move.import_nfe(
            auto, company_id, nfe, xml, False,
            company_id.l10n_br_allss_partner_automation,
            company_id.l10n_br_allss_invoice_automation, 
            company_id.l10n_br_allss_tax_automation,
            company_id.l10n_br_allss_supplierinfo_automation, 
            fiscal_position_id=company_id.l10n_br_allss_fiscal_position_id_automation or False, 
            account_move_dict=False,
            purchase_order_automation=company_id.l10n_br_allss_purchase_order_automation
        )

        if move and self.l10n_br_allss_picking_type_id:
            move.write({
                'l10n_br_allss_picking_type_id': self.l10n_br_allss_picking_type_id.id
            })
        
        return True if obj_account_move else False
    




    def l10n_br_allss_action_import_nfe_out_invoice(self, auto=False):
        _logger.warning(f'>>>>> ALLSS > NF-e Import > l10n_br_allss_action_import_nfe > self ({type(self)}): {self}')
        _logger.warning(f'>>>>> ALLSS > NF-e Import > l10n_br_allss_action_import_nfe > self.l10n_br_allss_import_batch_zip ({type(self.l10n_br_allss_import_batch_zip)}): {self.l10n_br_allss_import_batch_zip}')
        if not self.l10n_br_allss_nfe_xml and not self.l10n_br_allss_zip_file:
            # self.sudo().message_post(body='Por favor, insira um arquivo de NF-e!')
            if auto:
                _logger.warning(f'>>>>> ALLSS > NF-e Import > l10n_br_allss_action_import_nfe > Por favor, insira um arquivo de NF-e!')
                return False
            else:
                raise UserError('Por favor, insira um arquivo de NF-e!')

        xml_list = []
        if self.l10n_br_allss_import_batch_zip:
            try:
                _logger.warning(f'>>>>> ALLSS > NF-e Import > l10n_br_allss_action_import_nfe > Irá importar o arquivo ZIP!')
                xml_list = self._l10n_br_allss_unzip_xml_files()
                _logger.warning(f'>>>>> ALLSS > NF-e Import > l10n_br_allss_action_import_nfe > xml_list ({type(xml_list)}): {xml_list}')
            except Exception as e:
                # self.sudo().message_post(body='Esse não é um arquivo ZIP!')
                if auto:
                    _logger.warning(f'>>>>> ALLSS > NF-e Import > l10n_br_allss_action_import_nfe > Esse não é um arquivo ZIP!')
                    return False
                else:
                    raise ValidationError('Esse não é um arquivo ZIP!')
            if len(xml_list) == 0:
                # self.sudo().message_post(body='Nenhuma estrutura XML encontrada no arquivo!')
                if auto:
                    _logger.warning(f'>>>>> ALLSS > NF-e Import > l10n_br_allss_action_import_nfe > Nenhuma estrutura XML encontrada no arquivo!')
                    return False
                else:
                    raise UserError('Nenhuma estrutura XML encontrada no arquivo!')
        else:
            xml_list.append(
                {'name': 'NF-e', 'file': base64.b64decode(self.l10n_br_allss_nfe_xml)})
            _logger.warning(f'>>>>> 🔴 ALLSS > NF-e Import > l10n_br_allss_action_import_nfe > xml_list ({type(xml_list)}): {xml_list}')

        error_xml = []
        for xml in xml_list:
            try:
                ret = self._l10n_br_allss_import_xml_out_invoice(auto, xml['file'])
                _logger.warning(f'>>>>> 🔴 {ret} ')
                if not ret:
                    # return False
                    continue
            except (UserError, RedirectWarning, XMLSyntaxError, AttributeError) as e:
                msg = "Erro ao importar o xml: {0}\n{1}".format(
                    xml['name'], e.args[0])
                _logger.warning(msg)
                if self.l10n_br_allss_skip_wrong_xml and self.l10n_br_allss_import_batch_zip:
                    error_xml.append(xml)
                else:
                    # self.sudo().message_post(body=msg)
                    if auto:
                        _logger.warning(f'>>>>> ALLSS > NF-e Import > l10n_br_allss_action_import_nfe > msg ({type(msg)}): {msg}')
                        # return False
                        continue
                    else:
                        raise UserError(msg)
        _logger.warning(f'>>>>> ALLSS > NF-e Import > l10n_br_allss_action_import_nfe > error_xml ({type(error_xml)}): {error_xml}')
        if len(error_xml) > 0:
            self.state = 'error'
            self._l10n_br_allss_zip_xml_files(error_xml)
            return {
                "type": "ir.actions.act_window",
                "res_model": self._name,
                "views": [[False, "form"]],
                "name": "ALLSS Importação de NFe (Vendas)",
                "target": "inline",
                "res_id": self.id,
            }
        else:
            self.state = 'done'
        return True
