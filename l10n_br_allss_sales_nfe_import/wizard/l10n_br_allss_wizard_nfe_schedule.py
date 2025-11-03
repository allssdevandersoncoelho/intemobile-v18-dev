import re
import base64
import logging

_logger = logging.getLogger(__name__)

from lxml import objectify
from datetime import datetime
from ..service.mde import distribuicao_nfe
from odoo.exceptions import UserError
from odoo import models, api, fields, _
from dateutil.parser import parse
import pytz


class L10nBrAllssWizardNfeSchedule(models.TransientModel):
    _name = 'l10n.br.allss.wizard.nfe.schedule'
    _description = "Scheduler para efetuar download de notas"

    state = fields.Selection(
        string="Estado",
        selection=[('init', 'Não iniciado'), ('done', 'Finalizado')],
        default='init'
    )


    @staticmethod
    def _l10n_br_allss_mask_cnpj_cpf(cnpj_cpf):
        val = re.sub('[^0-9]', '', cnpj_cpf or '')
        if len(val) == 11:
            return "%s.%s.%s-%s" \
                   % (val[0:3], val[3:6], val[6:9], val[9:11])
        else:
            return "%s.%s.%s/%s-%s" \
                   % (val[0:2], val[2:5], val[5:8], val[8:12], val[12:14])


    @api.model
    def l10n_br_allss_schedule_download(self, raise_error=False):
        _logger.warning(f'>>>>>>>>>> ALLSS > l10n_br_allss_schedule_download > raise_error ({type(raise_error)}): {raise_error}')
        companies = self.env['res.company'].sudo().search([])
        _logger.warning(f'>>>>>>>>>> ALLSS > l10n_br_allss_schedule_download > companies ({type(companies)}): {companies}')
        total = 0
        messages = []
        for company in companies:
            _logger.warning(f'>>>>>>>>>> ALLSS > l10n_br_allss_schedule_download > company ({type(company)}): {company}')
            try:
                if not company.l10n_br_allss_cert_state == 'valid':
                    continue
                ms = self.env['ir.config_parameter'].sudo().get_param('l10n_br_allss_nfe_import.l10n_br_allss_ms_code_for_nfe_import')
                if not ms:
                    continue
                ms = self.env['l10n.br.allss.ms.line'].browse(int(ms))
                if not ms:
                    continue

                _logger.warning(f'>>>>>>>>>> ALLSS > l10n_br_allss_schedule_download > ms ({type(ms)}): {ms}')
                _logger.warning(f'>>>>>>>>>> ALLSS > l10n_br_allss_schedule_download > ms.get_ms_env() ({type(ms.get_ms_env())}): {ms.get_ms_env()}')
                env_type = 1 if ms.get_ms_env() == 'producao' else 2
                _logger.warning(f'>>>>>>>>>> ALLSS > l10n_br_allss_schedule_download > env_type ({type(env_type)}): {env_type}')
                _logger.warning(f'>>>>>>>>>> ALLSS > l10n_br_allss_schedule_download > nsu ({type(company.l10n_br_allss_last_nsu_nfe)}): {company.l10n_br_allss_last_nsu_nfe}')

                nfe_result = distribuicao_nfe(company, company.l10n_br_allss_last_nsu_nfe,
                                              **{'env_type': env_type})

                _logger.warning(f'>>>>>>>>>> ALLSS > l10n_br_allss_schedule_download > nfe_result ({type(nfe_result)}): {nfe_result}')

                message = "%s - %s / %s" % (
                    nfe_result['code'], nfe_result['message'],
                    company.name)
                
                _logger.warning(message)

                if nfe_result['code'] in (138, ):
                    env_mde = self.env['l10n.br.allss.nfe.mde']
                    for nfe in nfe_result['list_nfe']:
                        _logger.warning(f'>>>>>>>>>> ALLSS > l10n_br_allss_schedule_download > nfe ({type(nfe)}): {nfe}')
                        if nfe['schema'] == 'resNFe_v1.01.xsd':
                            total += 1
                            root = objectify.fromstring(nfe['xml'])
                            cnpj_cpf = 'CNPJ' in dir(root) and root.CNPJ.text or False
                            if not cnpj_cpf:
                                cnpj_cpf = root.CPF.text
                            cnpj_forn = self._l10n_br_allss_mask_cnpj_cpf(cnpj_cpf)

                            partner = self.env['res.partner'].sudo().search(
                                [('vat', '=', cnpj_forn)], limit=1)

                            total_mde = env_mde.sudo().search_count(
                                [('l10n_br_allss_nfe_key', '=', root.chNFe)])
                            if total_mde > 0:
                                continue

                            manifesto = {
                                'l10n_br_allss_nfe_key': root.chNFe,
                                'l10n_br_allss_nfe_number': str(root.chNFe)[25:34],
                                'l10n_br_allss_sequence_number': nfe['NSU'],
                                'l10n_br_allss_corporate_name': root.xNome,
                                'l10n_br_allss_operation_type': str(root.tpNF),
                                'l10n_br_allss_nfe_price_total': root.vNF,
                                'l10n_br_allss_nfe_situation': str(root.cSitNFe),
                                'state': 'pendente',
                                'l10n_br_allss_include_date': datetime.now(),
                                'l10n_br_allss_country_registry_vendor': cnpj_forn,
                                'l10n_br_allss_state_registry': root.IE,
                                'partner_id': partner.id,
                                'l10n_br_allss_emission_date': parse(
                                    str(root.dhEmi)).astimezone(pytz.utc).replace(tzinfo=None),
                                'company_id': company.id,
                                'l10n_br_allss_include_type': 'Verificação agendada'
                            }
                            
                            _logger.warning(f'>>>>>>>>>> ALLSS > l10n_br_allss_schedule_download > manifesto ({type(manifesto)}): {manifesto}')

                            obj_nfe = env_mde.sudo().create(manifesto)

                            file_name = 'resumo_nfe-%s.xml' % nfe['NSU']
                            self.env['ir.attachment'].sudo().create(
                                {
                                    'name': file_name,
                                    'datas': base64.b64encode(nfe['xml']),
                                    'description': u'NFe via manifesto',
                                    'res_model': 'l10n.br.allss.nfe.mde',
                                    'res_id': obj_nfe.id
                                })
                        elif nfe['schema'] in ('procNFe_v3.10.xsd',
                                               'procNFe_v4.00.xsd'):
                            total += 1
                            root = objectify.fromstring(nfe['xml'])
                            infNfe = root.NFe.infNFe
                            protNFe = root.protNFe.infProt
                            if hasattr(infNfe.emit, "CNPJ"):
                                cnpj_forn = self._l10n_br_allss_mask_cnpj_cpf(
                                    ('%014d' % infNfe.emit.CNPJ))
                            else:
                                cnpj_forn = self._l10n_br_allss_mask_cnpj_cpf(
                                    ('%011d' % infNfe.emit.CPF))
                                

                            partner = self.env['res.partner'].sudo().search(
                                [('vat', '=', cnpj_forn)], limit=1)

                            obj_nfe = env_mde.sudo().search(
                                [('l10n_br_allss_nfe_key', '=', protNFe.chNFe)], limit=1)
                            if obj_nfe:
                                obj_nfe.sudo().write({
                                    'state': 'ciente',
                                    'l10n_br_allss_nfe_xml': base64.encodebytes(nfe['xml']),
                                    'l10n_br_allss_nfe_xml_name': "NFe%08d.xml" % infNfe.ide.nNF,
                                })
                                _logger.warning(f'>>>>>>>>>> ALLSS > l10n_br_allss_schedule_download > obj_nfe 1 ({type(obj_nfe)}): {obj_nfe}')
                            else:
                                manifesto = {
                                    'l10n_br_allss_nfe_key': protNFe.chNFe,
                                    'l10n_br_allss_nfe_number': infNfe.ide.nNF,
                                    'l10n_br_allss_sequence_number': nfe['NSU'],
                                    'l10n_br_allss_corporate_name': infNfe.emit.xNome,
                                    'l10n_br_allss_operation_type': str(infNfe.ide.tpNF),
                                    'l10n_br_allss_nfe_price_total': infNfe.total.ICMSTot.vNF,
                                    'l10n_br_allss_nfe_situation': '',  # str(root.cSitNFe),
                                    'state': 'ciente',
                                    'l10n_br_allss_include_date': datetime.now(),
                                    'l10n_br_allss_country_registry_vendor': cnpj_forn,
                                    'l10n_br_allss_state_registry': infNfe.emit.IE,
                                    'partner_id': partner.id,
                                    'l10n_br_allss_emission_date': parse(
                                        str(infNfe.ide.dhEmi)).astimezone(pytz.utc).replace(
                                        tzinfo=None),
                                    'company_id': company.id,
                                    'l10n_br_allss_include_type': u'Verificação agendada',
                                    'l10n_br_allss_nfe_xml': base64.encodebytes(
                                        nfe['xml']),
                                    'l10n_br_allss_nfe_xml_name': "NFe%08d.xml" % infNfe.ide.nNF
                                }
                                
                                _logger.warning(f'>>>>>>>>>> ALLSS > l10n_br_allss_schedule_download > manifesto 2 ({type(manifesto)}): {manifesto}')
                                obj_nfe = env_mde.sudo().create(manifesto)
                                _logger.warning(f'>>>>>>>>>> ALLSS > l10n_br_allss_schedule_download > obj_nfe 2 ({type(obj_nfe)}): {obj_nfe}')

                            file_name = 'resumo_nfe-%s.xml' % nfe['NSU']

                        company.l10n_br_allss_last_nsu_nfe = nfe['NSU']
                elif nfe_result['code'] in (137, ):
                    continue
                else:
                    messages += [message]

                self._cr.commit()
            except UserError as e:
                if raise_error:
                    raise UserError(f'Erro na consulta: \n{e}')
                else:
                    _logger.warning(f'>>>>>>>>>> ALLSS > l10n_br_allss_schedule_download > Erro e ({type(e)}): {e}')
            except Exception as e:
                _logger.error("Erro ao consultar Manifesto", exc_info=True)
                if raise_error:
                    raise UserError(f'Não foi possivel efetuar a consulta!\nCheque o log\n\n{e}')
                else:
                    _logger.warning(f'>>>>>>>>>> ALLSS > l10n_br_allss_schedule_download > Exception e ({type(e)}): {e}')
        if raise_error:
            # title_message = '👍 Obtenção dos arquivos XML concluída!'
            # message = f'Foram localizados {total} documentos!\n{messages}'
            # return {'warning': {'title': _(title_message), 'message': _(message)} }
            _logger.warning(f'>>>>>>>>>> ALLSS > l10n_br_allss_schedule_download > Total de documentos localizados: {total}\n{messages}')
            raise UserError('Total de documentos localizados %s\n%s' % (
                total, '\n'.join(messages)))
        else:
            _logger.warning(f'>>>>>>>>>> ALLSS > l10n_br_allss_schedule_download > Total de documentos localizados: {total}\n{messages}')


    def l10n_br_allss_execute_download(self):
        self.l10n_br_allss_schedule_download(raise_error=True)
        return {'type': 'ir.actions.act_window_close'}


    @api.model
    def l10n_br_allss_cron_manifest_automation(self, auto=True, process=3):
        ''' Rotina de execução automática do DF-e, relativo a manifestação do destinatário.
        Conforme a escolha do processo, a rotina poderá:\n
            1- Buscar os arquivos XML da NF-e e Efetuar o download dos arquivos XML da NF-e;\n
            2- Efetuar a importação do arquivo XML da NF-e para a geração da Fatura;\n
            3- Executar os processos 1 e 2 na sequencia.

        :param auto:        True indica se a rotina será executada via agendador de tarefas, sem interação com o Usuário (default True).
        :param process:     Indica o código do processo a ser executado, nas opções de 1 a 3 inficado acima (default 3).
        
        :return:            Sem retorno esperado.
        '''
        companies = self.env['res.company'].sudo().search([])
        _logger.warning(f'>>>>>>>>>> ALLSS > l10n_br_allss_cron_manifest_automation > companies ({type(companies)}): {companies}')
        for company in companies:
            _logger.warning(f'>>>>>>>>>> ALLSS > l10n_br_allss_cron_manifest_automation > company ({type(company)}): {company}')
            if not company.l10n_br_allss_manifest_automation:
                continue
            
            registers_limit = int(self.env['ir.config_parameter'].sudo().\
                                  get_param('l10n_br_allss_nfe_import.l10n_br_allss_nfe_import_nfe_mde_limit_for_process','50'))

            _logger.warning(f'>>>>>>>>>> ALLSS > l10n_br_allss_cron_manifest_automation > registers_limit ({type(registers_limit)}): {registers_limit}')

            if process == 1 or process == 3:
                manifestos = self.env['l10n.br.allss.nfe.mde'].sudo().search(
                    [('company_id', '=', company.id),
                    ('l10n_br_allss_is_processed', '=', False)], limit=registers_limit)
                _logger.warning(f'>>>>>>>>>> ALLSS > l10n_br_allss_cron_manifest_automation > manifestos 1 ou 3 ({type(manifestos)}): {manifestos}')
            else:
                manifestos = self.env['l10n.br.allss.nfe.mde'].sudo().search(
                    [('company_id', '=', company.id),
                    ('l10n_br_allss_is_imported', '=', False)], limit=registers_limit)
                _logger.warning(f'>>>>>>>>>> ALLSS > l10n_br_allss_cron_manifest_automation > manifestos 2 ({type(manifestos)}): {manifestos}')
            for manifesto in manifestos:
                _logger.warning(f'>>>>>>>>>> ALLSS > l10n_br_allss_cron_manifest_automation > manifesto ({type(manifesto)}): {manifesto}')
                try:
                    if process == 1 or process == 3:
                        _logger.warning(f'>>>>>>>>>> ALLSS > l10n_br_allss_cron_manifest_automation > process 1 or 3 > Iniciando Ciência da Operação...')
                        if not manifesto.l10n_br_allss_action_known_emission():
                            continue
                        _logger.warning(f'>>>>>>>>>> ALLSS > l10n_br_allss_cron_manifest_automation > process 1 or 3 > Iniciando Download...')
                        if not manifesto.l10n_br_allss_action_download_xml():
                            continue
                        manifesto.sudo().write({'l10n_br_allss_is_processed': True})
                        self._cr.commit()
                    if process == 2 or process == 3:
                        _logger.warning(f'>>>>>>>>>> ALLSS > l10n_br_allss_cron_manifest_automation > process 2 or 3 > Iniciando Importação do XML...')
                        if not manifesto.l10n_br_allss_action_import_xml(auto):
                            continue
                        manifesto.sudo().write({'l10n_br_allss_is_imported': True})
                        self._cr.commit()
                except Exception as e:
                    _logger.error(f">>>>>>>>>> ALLSS > l10n_br_allss_cron_manifest_automation > Erro ao processar manifesto. Erro: {e} ", exc_info=True)
                    manifesto.message_post(
                        body='Não foi possível processar o manifesto \
                        completamente: %s' % e.name if 'name' in e else f'{e}')
                    continue
                # finally:
                #     _logger.error(f">>>>>>>>>> ALLSS > l10n_br_allss_cron_manifest_automation > Processado!")
                #     manifesto.l10n_br_allss_is_processed = True
                #     self._cr.commit()
            _logger.warning(f">>>>>>>>>> ALLSS > l10n_br_allss_cron_manifest_automation > Fim!")
