# -*- coding: utf-8 -*-
# © 2023 Tiago Prates <tiago.prates@allss.com.br>, ALLSS Soluções em Sistemas LTDA
# License AGPL-3.0 or later (http://www.gnu.org/licenses/agpl.html)

import base64
import logging

_logger = logging.getLogger(__file__)

from os import path
from zipfile import ZipFile
from io import BytesIO
from lxml import objectify
from lxml.etree import XMLSyntaxError

from odoo import api, models, fields
from odoo.exceptions import UserError, RedirectWarning, ValidationError



class L10nBrAlssWizardNfeImport(models.TransientModel):
    _name = 'l10n.br.allss.wizard.nfe.import'
    # _inherit = ['mail.thread', 'mail.activity.mixin']
    _description = 'Controle de importação de NF-e (XML)'

    state = fields.Selection([('ok', 'OK'), ('error', 'Erro'), ('done', 'Concluído')], default='ok')
    l10n_br_allss_import_batch_zip = fields.Boolean(
        string="Importar Zip?", help="Se marcado esta opção é possível \
        importar um arquivo compactado com vários arquivos. Apenas arquivos \
        com a extensão .xml serão importados")
    l10n_br_allss_nfe_xml = fields.Binary('XML da NFe')
    l10n_br_allss_zip_file = fields.Binary('Arquivo ZIP')
    l10n_br_allss_zip_file_error = fields.Binary('Arquivos não importados!', readonly=True)
    l10n_br_allss_zip_file_error_name = fields.Char(
        default="XMLs não importados.zip", readonly=True)
    l10n_br_allss_skip_wrong_xml = fields.Boolean(
        string="Ignorar Xml com erro?", help="Se marcado vai ignorar os xmls \
        que estão com erro e importar o restante! Os xmls com erro serão \
        disponibilizados para download", default=True)

    def _l10n_br_allss_unzip_xml_files(self):
        _logger.warning(f'>>>>> ALLSS > NF-e Import > _l10n_br_allss_unzip_xml_files > self.l10n_br_allss_zip_file ({type(self.l10n_br_allss_zip_file)}): {self.l10n_br_allss_zip_file}')
        zip_memory = base64.b64decode(self.l10n_br_allss_zip_file)
        _logger.warning(f'>>>>> ALLSS > NF-e Import > _l10n_br_allss_unzip_xml_files > zip_memory ({type(zip_memory)}): {zip_memory}')
        xml_list = []

        with ZipFile(BytesIO(zip_memory)) as thezip:
            _logger.warning(f'>>>>> ALLSS > NF-e Import > _l10n_br_allss_unzip_xml_files > thezip ({type(thezip)}): {thezip}')
            for zipinfo in thezip.infolist():
                if not zipinfo.filename.lower().endswith('.xml'):
                    continue
                with thezip.open(zipinfo) as thefile:
                    xml_list.append(
                        {'name': path.basename(zipinfo.filename),
                         'file': thefile.read()})
        _logger.warning(f'>>>>> ALLSS > NF-e Import > _l10n_br_allss_unzip_xml_files > xml_list ({type(xml_list)}): {xml_list}')
        return xml_list

    def _l10n_br_allss_zip_xml_files(self, xml_list):
        mem_file = BytesIO()
        with ZipFile(mem_file, mode='w') as thezip:
            for xml in xml_list:
                with thezip.open(xml['name'], mode='w') as thefile:
                    thefile.write(xml['file'])
        self.l10n_br_allss_zip_file_error = base64.encodebytes(mem_file.getvalue())

    def _l10n_br_allss_import_xml(self, auto, xml):
        nfe = objectify.fromstring(xml)
        obj_account_move = self.env.get('account.move').sudo()
        company_id = self.env.company.sudo()
        
        _logger.warning(f'>>>>> 🔴 nfe{nfe} --- xml {xml} ')
        _logger.warning(f'>>>>>>>>>> ALLSS > _l10n_br_allss_import_xml > company_id ({type(company_id)}): {company_id}')
        _logger.warning(f'>>>>>>>>>> ALLSS > _l10n_br_allss_import_xml > company_id.l10n_br_allss_fiscal_position_id_automation ({type(company_id.l10n_br_allss_fiscal_position_id_automation )}): {company_id.l10n_br_allss_fiscal_position_id_automation }')

        obj_account_move.import_nfe(
            auto, company_id, nfe, xml, False,
            company_id.l10n_br_allss_partner_automation,
            company_id.l10n_br_allss_invoice_automation, 
            company_id.l10n_br_allss_tax_automation,
            company_id.l10n_br_allss_supplierinfo_automation, 
            fiscal_position_id=company_id.l10n_br_allss_fiscal_position_id_automation or False, 
            account_move_dict=False,
            purchase_order_automation=company_id.l10n_br_allss_purchase_order_automation
        )
        _logger.warning(f'>>>>> 🔴 obj_account_move: {obj_account_move}')
        if not obj_account_move:
            return False
        else:
            return True

    def l10n_br_allss_action_import_nfe(self, auto=False):
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
                ret = self._l10n_br_allss_import_xml(auto, xml['file'])
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
                "name": "ALLSS Importação de NFe",
                "target": "inline",
                "res_id": self.id,
            }
        else:
            self.state = 'done'
        return True
