# Implementações de CcpBusiness

**254** implementações (diretas e indiretas). Média: **2.196,38 bytes** e **50,09 linhas**. Acima da média: 77 em bytes e 75 em linhas.

Por tipo: classe 146 · item de enum 69 · classe aninhada 38 · classe abstrata 1.

Por projeto: vis_business_jobsnow 95 · ccp_rest-api-tests_jobsnow 67 · jn_business_jobsnow 31 · js_business_jobsnow 28 · jb_business_jobsnow 19 · ccp_commons_jobsnow 8 · ccp_db-crud_elasticsearch 4 · ccp_db-query_elasticsearch 2.

Nomes simples repetidos em pacotes diferentes, identificados pelo pacote na coluna Nome: EchoTask, FakeBot, NoopBusiness.

`(acima)` = acima da média geral. Uma tabela por projeto, do que tem mais implementações para o que tem menos, cada uma ordenada por bytes.

### vis_business_jobsnow · 95 implementações · 296.498 bytes · 6.255 linhas

| # | Nome | Tipo | Bytes | Linhas |
|--:|---|---|--:|--:|
| 1 | VisBusinessSendResumesToRecruiters | classe | 23.502 (acima) | 466 (acima) |
| 2 | VisBusinessBuildResumeRow | classe | 21.113 (acima) | 440 (acima) |
| 3 | VisSupportSkillFixHierarchyShowRequest | classe | 15.508 (acima) | 292 (acima) |
| 4 | VisServiceSkills.GetSkillsFromText | enum | 10.775 (acima) | 250 (acima) |
| 5 | VisBusinessRenderResumesTable | classe | 9.822 (acima) | 211 (acima) |
| 6 | VisBusinessSkillFixHierarchyReview | classe | 8.561 (acima) | 172 (acima) |
| 7 | VisBusinessViewedResumeDetails | classe | 7.841 (acima) | 166 (acima) |
| 8 | VisBusinessLoadRecruitersFromHtmlFolder | classe | 7.834 (acima) | 166 (acima) |
| 9 | VisBusinessSkillFixHierarchyIgnoreUser | classe | 5.766 (acima) | 109 (acima) |
| 10 | JnSupportIgnoredUsersChoose | classe | 5.590 (acima) | 110 (acima) |
| 11 | VisBusinessResumeViewersOfTheMonth | classe | 5.242 (acima) | 102 (acima) |
| 12 | VisSupportSkillSuggestionDecide | classe | 4.595 (acima) | 79 (acima) |
| 13 | VisSupportSkillFixHierarchyChooseMode | classe | 4.496 (acima) | 83 (acima) |
| 14 | VisBusinessViewedResumesOfTheMonth | classe | 4.354 (acima) | 82 (acima) |
| 15 | VisSupportSkillFixHierarchyDecideItem | classe | 4.220 (acima) | 76 (acima) |
| 16 | VisBusinessSaveRecruiterFromLoginAnswers | classe | 4.144 (acima) | 82 (acima) |
| 17 | VisBusinessSkillFixHierarchyRefuseAlreadyReviewed | classe | 4.015 (acima) | 95 (acima) |
| 18 | VisBusinessDiscardPendingRequestsOfIgnoredUser | classe | 3.948 (acima) | 83 (acima) |
| 19 | VisServiceSkillSuggestion.SuggestSkill | enum | 3.927 (acima) | 66 (acima) |
| 20 | VisBusinessSkillSuggestionApply | classe | 3.679 (acima) | 83 (acima) |
| 21 | VisBusinessDeleteFixHierarchyItemIfOrphan | classe | 3.653 (acima) | 86 (acima) |
| 22 | VisBusinessLoadSkillRankings | classe | 3.635 (acima) | 84 (acima) |
| 23 | VisBusinessSkillFixHierarchyItem | classe | 3.566 (acima) | 77 (acima) |
| 24 | VisSupportSkillFixHierarchyConfirmIgnore | classe | 3.484 (acima) | 60 (acima) |
| 25 | VisSupportSkillSuggestionConfirmIgnore | classe | 3.414 (acima) | 59 (acima) |
| 26 | VisBusinessResumeLinkedinRelease | classe | 3.391 (acima) | 73 (acima) |
| 27 | VisSupportSkillSuggestionShowRequest | classe | 3.375 (acima) | 67 (acima) |
| 28 | VisJsonTransformerRecruiterProfessional | classe | 3.313 (acima) | 73 (acima) |
| 29 | VisBusinessDefaultResumeAlias | classe | 3.252 (acima) | 67 (acima) |
| 30 | VisNotifySupportAndUserAboutPendingSkillHierarchyRequest | aninhada | 3.249 (acima) | 58 (acima) |
| 31 | VisBusinessSaveSkillSuggestionWithSynonyms | classe | 3.222 (acima) | 71 (acima) |
| 32 | VisServiceSkillSuggestion.GetSkillSuggestion | enum | 3.143 (acima) | 61 (acima) |
| 33 | VisBusinessSkillFixHierarchyDeleteOrphanItems | classe | 3.037 (acima) | 71 (acima) |
| 34 | VisServiceResume.ChangeStatus | enum | 2.980 (acima) | 61 (acima) |
| 35 | VisBusinessResumeLinkedinOwner | classe | 2.929 (acima) | 64 (acima) |
| 36 | VisBusinessSkillFixHierarchyCreateItems | classe | 2.819 (acima) | 53 (acima) |
| 37 | VisBusinessSaveUserIgnoredInSkillSuggestion | classe | 2.808 (acima) | 49 |
| 38 | VisJsonTransformerPutEmailHashAndDomainRecruiter | classe | 2.784 (acima) | 62 (acima) |
| 39 | VisBusinessCountTheFirstViewOfTheResume | classe | 2.735 (acima) | 53 (acima) |
| 40 | VisBusinessTransferFixHierarchyRequestToFulfiled | classe | 2.722 (acima) | 55 (acima) |
| 41 | VisJsonTransformerLinkedinHash | classe | 2.692 (acima) | 67 (acima) |
| 42 | VisBusinessChangeTheSkillAndTheLookup | classe | 2.557 (acima) | 63 (acima) |
| 43 | VisBusinessSkillSuggestionIgnoreUser | classe | 2.543 (acima) | 58 (acima) |
| 44 | VisJsonTransformerSpokenLanguageWithoutId | classe | 2.536 (acima) | 65 (acima) |
| 45 | VisBusinessTransferSkillSuggestionWithTheDecision | classe | 2.447 (acima) | 49 |
| 46 | VisBusinessSkillSuggestionReview | classe | 2.444 (acima) | 54 (acima) |
| 47 | VisServiceCompany.SearchCompaniesByTheirFirstThreeInitials | enum | 2.303 (acima) | 47 |
| 48 | VisBusinessPrepareRecruiter | classe | 2.245 (acima) | 46 |
| 49 | VisServicePosition.SuggestNewSkills | enum | 2.219 (acima) | 42 |
| 50 | VisJsonTransformerExperienceStartYear | classe | 2.122 | 55 (acima) |
| 51 | VisServiceRecruiterResumes.ViewResumeFromEmail | enum | 2.105 | 37 |
| 52 | VisJsonTransformerRecruiterDomain | classe | 1.997 | 56 (acima) |
| 53 | VisBusinessMoveFixHierarchyItem | classe | 1.981 | 41 |
| 54 | VisBusinessDeleteStoredFixHierarchyRequest | classe | 1.927 | 42 |
| 55 | VisServiceResume.GetData | enum | 1.922 | 41 |
| 56 | JnSupportAllowCommandToUser | classe | 1.901 | 43 |
| 57 | JnSupportIgnoredUsersShow | classe | 1.880 | 45 |
| 58 | VisBusinessDeleteStoredSkillSuggestion | classe | 1.834 | 41 |
| 59 | VisBusinessSaveFixHierarchyRequestAndSpendTheDay | classe | 1.804 | 42 |
| 60 | VisBusinessCollectPendingFixHierarchyRequest | classe | 1.771 | 39 |
| 61 | VisBusinessAddMissingSynonymsToSkill | classe | 1.768 | 45 |
| 62 | VisBusinessCreateApprovedSkill | classe | 1.639 | 48 |
| 63 | VisBusinessSkillFixHierarchyNotifyAlreadyReviewed | classe | 1.531 | 33 |
| 64 | VisNotifySupportAndUserAboutPendingSkillRequest | aninhada | 1.515 | 28 |
| 65 | VisServiceSkillFixHierarchy.FixSkillHierarchy | enum | 1.515 | 29 |
| 66 | VisBusinessChangeOnlyTheSkillLookup | classe | 1.501 | 46 |
| 67 | VisBusinessRefuseResumeNotFound | classe | 1.416 | 40 |
| 68 | VisBusinessInsertRecruiterWhenNotFound | classe | 1.291 | 38 |
| 69 | VisServicePosition.GetData | enum | 1.266 | 26 |
| 70 | VisServiceSkillFixHierarchy.GetSkillFixHierarchy | enum | 1.159 | 27 |
| 71 | VisBusinessSkillSuggestionShareRejection | classe | 1.122 | 27 |
| 72 | VisBusinessSkillSuggestionShareApproval | classe | 1.119 | 27 |
| 73 | VisServiceSkillFixHierarchy.DeleteSkillFixHierarchy | enum | 835 | 19 |
| 74 | VisServiceSkillSuggestion.DeleteSkillSuggestion | enum | 812 | 19 |
| 75 | VisServiceRecruiterResumes.SaveResumeAliasFromEmail | enum | 811 | 15 |
| 76 | VisNotifySupportAboutSharedLinkedin | aninhada | 803 | 17 |
| 77 | VisServiceRecruiterResumes.UnsubscribeFromResumesEmail | enum | 788 | 17 |
| 78 | VisNotifyUserAboutDeactivatedResume | aninhada | 755 | 17 |
| 79 | VisNotifyUserAboutReactivatedResume | aninhada | 755 | 17 |
| 80 | VisNotifyUserAboutAlreadyReviewedSkillHierarchy | aninhada | 745 | 16 |
| 81 | VisNotifyUserAboutDeletedResume | aninhada | 739 | 17 |
| 82 | VisNotifyUserAboutSavedResume | aninhada | 726 | 17 |
| 83 | VisNotifyUserAboutFulfiledSkillHierarchy | aninhada | 716 | 16 |
| 84 | VisNotifyUserAboutRejectedSkill | aninhada | 677 | 16 |
| 85 | VisNotifyUserAboutAprovedSkill | aninhada | 673 | 16 |
| 86 | VisServiceResume.GetViewersOfTheMonth | enum | 645 | 19 |
| 87 | VisServiceRecruiterResumes.GetResumesOfTheWeek | enum | 631 | 10 |
| 88 | VisServiceResume.Delete | enum | 584 | 20 |
| 89 | VisServiceResume.Save | enum | 583 | 21 |
| 90 | VisNotifyRecruiterAboutResumes | aninhada | 576 | 15 |
| 91 | VisServicePosition.ChangeStatus | enum | 260 | 12 |
| 92 | VisServicePosition.Save | enum | 230 | 12 |
| 93 | VisServiceRecruiterResumes.GetViewedResumesOfTheMonth | enum | 216 | 6 |
| 94 | VisServicePosition.GetImportantSkillsFromText | enum | 215 | 11 |
| 95 | VisServiceRecruiterResumes.GetViewedResumeDetails | enum | 208 | 6 |

### ccp_rest-api-tests_jobsnow · 67 implementações · 32.202 bytes · 1.049 linhas

| # | Nome | Tipo | Bytes | Linhas |
|--:|---|---|--:|--:|
| 1 | SynonymKeyAndRecordCollector | classe | 1.202 | 32 |
| 2 | FakeBot (com.jb.instant.messenger.reader) | classe | 1.010 | 34 |
| 3 | DefaultValueProducer | classe | 988 | 25 |
| 4 | TemporaryReplacementCacheCheck | classe | 974 | 30 |
| 5 | FlowRecoveryDisturbingHandler | classe | 967 | 29 |
| 6 | FlowRecoveryMainProcess | classe | 916 | 31 |
| 7 | TemporaryReplacementGreeting | classe | 900 | 23 |
| 8 | DefaultValueBusiness | classe | 835 | 27 |
| 9 | FlowRecoveryNext | classe | 789 | 27 |
| 10 | BusinessFieldTypeString | classe | 755 | 23 |
| 11 | FlowRecoveryFixer | classe | 718 | 27 |
| 12 | BusinessCopyFieldValidationsFrom | classe | 687 | 20 |
| 13 | JnReceiverTask | classe | 685 | 22 |
| 14 | BusinessFieldTypeNumberUnsigned | classe | 681 | 20 |
| 15 | FlowRecoveryCallRecorder | classe | 676 | 26 |
| 16 | BusinessFieldTypeNumberInteger | classe | 675 | 20 |
| 17 | BusinessFieldTypeNestedJson | classe | 657 | 20 |
| 18 | BusinessFieldTypeTimeBefore | classe | 657 | 20 |
| 19 | BusinessFieldTypeTimeAfter | classe | 651 | 20 |
| 20 | LoginActions.readTokenFromReceivedEmail | enum | 649 | 13 |
| 21 | BusinessValidatorRequired | classe | 645 | 20 |
| 22 | BusinessFieldTypeBoolean | classe | 639 | 20 |
| 23 | BusinessFieldTypeCustom | classe | 633 | 20 |
| 24 | BusinessFieldTypeNumber | classe | 633 | 20 |
| 25 | BusinessValidatorArray | classe | 627 | 20 |
| 26 | TemporaryReplacementFailingBusiness | classe | 622 | 17 |
| 27 | LimitReachedRecorder | classe | 606 | 22 |
| 28 | CcpCachedServiceTestStubService | classe | 514 | 19 |
| 29 | CcpServiceTestStubService | classe | 484 | 19 |
| 30 | FailingExecutor | aninhada | 447 | 22 |
| 31 | EchoService | aninhada | 440 | 18 |
| 32 | UnrecordedTask | aninhada | 410 | 14 |
| 33 | RecordingTask | aninhada | 403 | 16 |
| 34 | NamingService | aninhada | 399 | 19 |
| 35 | NoopExecutor | classe | 365 | 12 |
| 36 | NoopBusiness (com.ccp.rest.api.spring.servlet.filters) | classe | 361 | 14 |
| 37 | JnSendMessageToUserFluentTestNoopBusiness | classe | 356 | 10 |
| 38 | CountingService | aninhada | 354 | 13 |
| 39 | EchoTask (com.ccp.topic.consumer.pubsub.pull) | aninhada | 349 | 10 |
| 40 | EchoTask (com.jn.mensageria) | aninhada | 349 | 10 |
| 41 | BotBusinessForTest | classe | 344 | 13 |
| 42 | JnSendMessageToUserTestNoopBusiness | classe | 344 | 10 |
| 43 | NoopBusiness (com.jn.entities) | classe | 344 | 14 |
| 44 | NoopBusiness (com.jn.mensageria) | classe | 339 | 14 |
| 45 | ThrowsTheSubclass | aninhada | 338 | 10 |
| 46 | RecordedTask | aninhada | 336 | 11 |
| 47 | FailingTask | aninhada | 335 | 10 |
| 48 | ReturnsNullBusiness | classe | 329 | 13 |
| 49 | RecordHandled | aninhada | 328 | 11 |
| 50 | RecordSecond | aninhada | 323 | 11 |
| 51 | RecordFirst | aninhada | 318 | 11 |
| 52 | RecordTwin | aninhada | 313 | 11 |
| 53 | NoopSender | classe | 309 | 13 |
| 54 | RefusingTask | aninhada | 306 | 8 |
| 55 | NoopBusiness (com.ccp.business) | classe | 301 | 13 |
| 56 | Impl | classe | 282 | 13 |
| 57 | Echo | aninhada | 268 | 10 |
| 58 | LoginActions.renameTokenField | enum | 245 | 6 |
| 59 | AcceptingTask | aninhada | 225 | 8 |
| 60 | CapturingTask | aninhada | 202 | 8 |
| 61 | LoginActions.ExecuteLogin | enum | 88 | 1 |
| 62 | LoginActions.CreateLoginToken | enum | 76 | 1 |
| 63 | LoginActions.ExecuteLogout | enum | 68 | 1 |
| 64 | LoginActions.CreateLoginEmail | enum | 43 | 1 |
| 65 | LoginActions.SavePassword | enum | 42 | 1 |
| 66 | LoginActions.SaveAnswers | enum | 40 | 1 |
| 67 | NoopJnService.INSTANCE | enum | 8 | 1 |

### jn_business_jobsnow · 31 implementações · 88.712 bytes · 2.069 linhas

| # | Nome | Tipo | Bytes | Linhas |
|--:|---|---|--:|--:|
| 1 | JnSendMessageToUser | classe | 22.765 (acima) | 516 (acima) |
| 2 | JnFunctionMensageriaSender | classe | 9.413 (acima) | 217 (acima) |
| 3 | JnBusinessDeleteVersionableRecords | classe | 5.923 (acima) | 138 (acima) |
| 4 | JnBusinessSendHttpRequest | classe | 5.510 (acima) | 113 (acima) |
| 5 | JnMessageType.instantMessenger | enum | 4.967 (acima) | 112 (acima) |
| 6 | JnBusinessCancelSupportPendingCommand | classe | 4.723 (acima) | 92 (acima) |
| 7 | JnBusinessRegisterSupportPendingCommand | classe | 3.322 (acima) | 69 (acima) |
| 8 | JnBusinessPublishWriteEvent | abstrata | 2.899 (acima) | 65 (acima) |
| 9 | JnJsonTransformersFieldEntityFieldCalculateHash | classe | 2.692 (acima) | 79 (acima) |
| 10 | JnMessageType.email | enum | 2.490 (acima) | 56 (acima) |
| 11 | JnJsonTransformersFieldEntityMessageHash | classe | 2.241 (acima) | 58 (acima) |
| 12 | JnBusinessPublishToTheWriteEventSubscribers | classe | 2.037 | 46 |
| 13 | JnDeleteKeysFromCache | classe | 2.036 | 58 (acima) |
| 14 | JnBusinessValidateSession | classe | 1.607 | 36 |
| 15 | JnInstantMessageType.file | enum | 1.556 | 27 |
| 16 | JnBusinessEntityFieldsOfTheJson | classe | 1.423 | 39 |
| 17 | JnJsonTransformersFieldsEntityDefault.password | enum | 1.305 | 35 |
| 18 | JnJsonTransformersFieldsEntityDoNothing | classe | 1.278 | 43 |
| 19 | JnServiceAsyncTask.GetAsyncTaskStatusById | enum | 1.215 | 25 |
| 20 | JnJsonTransformersFieldsEntityDefault.token | enum | 1.207 | 33 |
| 21 | JnInstantMessageType.text | enum | 1.183 | 21 |
| 22 | JnJsonTransformersFieldsEntityDefault.email | enum | 1.153 | 30 |
| 23 | JnNotifyUserAboutLoginToken | aninhada | 882 | 19 |
| 24 | JnJsonTransformersFieldsEntityDefault.timestamp | enum | 846 | 27 |
| 25 | JnJsonTransformersFieldsEntityDefault.tokenHash | enum | 821 | 23 |
| 26 | JnNotifySupportAboutPendingLockedLoginToken | aninhada | 539 | 15 |
| 27 | JnNotifySupportAboutPendingResendLoginToken | aninhada | 539 | 15 |
| 28 | JnNotifySupportAboutAnError | aninhada | 536 | 16 |
| 29 | JnNotifySupportAboutSolvedLockedLoginToken | aninhada | 535 | 15 |
| 30 | JnNotifySupportAboutSolvedResendLoginToken | aninhada | 535 | 15 |
| 31 | JnNotifySupportAboutWaring | aninhada | 534 | 16 |

### js_business_jobsnow · 28 implementações · 60.963 bytes · 1.320 linhas

| # | Nome | Tipo | Bytes | Linhas |
|--:|---|---|--:|--:|
| 1 | JsBusinessEvaluateAttempts | classe | 6.630 (acima) | 159 (acima) |
| 2 | JsBusinessValidateLogin | classe | 4.924 (acima) | 98 (acima) |
| 3 | JsBusinessResetLoginToken | classe | 4.683 (acima) | 107 (acima) |
| 4 | JsBusinessSavePassword | classe | 3.847 (acima) | 82 (acima) |
| 5 | JsBusinessCheckCurrentSession | classe | 3.509 (acima) | 69 (acima) |
| 6 | JsServiceLogin.ExecuteLogin | enum | 3.387 (acima) | 59 (acima) |
| 7 | JsBusinessRefuseExpiredSession | classe | 3.144 (acima) | 58 (acima) |
| 8 | JsBusinessRefuseSessionOfAnotherClient | classe | 2.730 (acima) | 51 (acima) |
| 9 | JsServiceLogin.CreateLoginToken | enum | 2.478 (acima) | 48 |
| 10 | JsBusinessPrepareLoginTokenBeforeSave | classe | 2.477 (acima) | 46 |
| 11 | JsBusinessExecuteLogin | classe | 2.410 (acima) | 59 (acima) |
| 12 | JsBusinessIncrementSessionTokenAttempts | classe | 2.336 (acima) | 58 (acima) |
| 13 | JsServiceLogin.SavePassword | enum | 1.823 | 35 |
| 14 | JsBusinessExecuteLogout | classe | 1.805 | 49 |
| 15 | JsSupportLoginToken | classe | 1.631 | 48 |
| 16 | LoadDataAboutToken | classe | 1.461 | 33 |
| 17 | JsServiceLogin.CreateLoginEmail | enum | 1.384 | 22 |
| 18 | JsServiceLogin.UnlockLoginToken | enum | 1.309 | 32 |
| 19 | JsServiceLogin.ExistsLoginEmail | enum | 1.308 | 22 |
| 20 | JsServiceLogin.SaveAnswers | enum | 1.299 | 24 |
| 21 | JsServiceLogin.ResendLoginToken | enum | 1.290 | 34 |
| 22 | JsBusinessResetSessionTokenAttempts | classe | 1.237 | 37 |
| 23 | JsonTransformer | classe | 983 | 27 |
| 24 | JsJsonTransformersFieldEntityTokenHash | classe | 963 | 20 |
| 25 | JsServiceLogin.ExecuteLogout | enum | 942 | 23 |
| 26 | JsBusinessPublishLoginAnswersSaved | classe | 769 | 18 |
| 27 | JsSupportLoginTokenTypes.resendToken | enum | 102 | 1 |
| 28 | JsSupportLoginTokenTypes.unlockToken | enum | 102 | 1 |

### jb_business_jobsnow · 19 implementações · 64.719 bytes · 1.613 linhas

| # | Nome | Tipo | Bytes | Linhas |
|--:|---|---|--:|--:|
| 1 | Bot | classe | 17.473 (acima) | 426 (acima) |
| 2 | BotCommand | classe | 12.249 (acima) | 321 (acima) |
| 3 | BotCommandStep | classe | 10.488 (acima) | 262 (acima) |
| 4 | JbSupportPendingTicketsChoose | classe | 5.369 (acima) | 108 (acima) |
| 5 | JbDefaultBotCommandStep.setLanguage | enum | 4.642 (acima) | 94 (acima) |
| 6 | JbDefaultBotCommandStep.explainThisCommand | enum | 2.063 | 51 (acima) |
| 7 | JbDefaultBotCommandStep.exit | enum | 1.924 | 39 |
| 8 | JbSupportPendingTicketsShow | classe | 1.802 | 44 |
| 9 | BotCommandStepUpdateSession | classe | 1.463 | 43 |
| 10 | BotNewSessionProducer | classe | 1.425 | 44 |
| 11 | JsonProducers.putCommandNameWhenHasNoSession | enum | 1.019 | 34 |
| 12 | JbDefaultBotCommandStep.showAllCommands | enum | 1.010 | 28 |
| 13 | JsonProducers.sessionValuesProducer | enum | 894 | 22 |
| 14 | JbDefaultBotCommandStep.explainThisBot | enum | 746 | 24 |
| 15 | JbDefaultBotCommandStep.removeSession | enum | 712 | 23 |
| 16 | JsonProducers.handleInnerJson | enum | 433 | 12 |
| 17 | JbDefaultBotCommandStep.chatId | enum | 372 | 13 |
| 18 | JsonProducers.createInnerJson | enum | 352 | 13 |
| 19 | JsonProducers.getInnerJson | enum | 283 | 12 |

### ccp_commons_jobsnow · 8 implementações · 9.403 bytes · 276 linhas

| # | Nome | Tipo | Bytes | Linhas |
|--:|---|---|--:|--:|
| 1 | FunctionPutStatus | classe | 1.681 | 43 |
| 2 | FunctionPutEntity | classe | 1.412 | 38 |
| 3 | CcpBusinessDeleteStoredRecordFromEntity | classe | 1.267 | 34 |
| 4 | CcpEntityThrowNotFound | classe | 1.196 | 35 |
| 5 | CcpBusinessDeleteRecordFromEntity | classe | 1.094 | 37 |
| 6 | CcpBusinessThrowFlowDisturb | classe | 924 | 32 |
| 7 | CcpFunctionThrowException | classe | 921 | 32 |
| 8 | CcpJsonFieldDefaultValueDoNothing | classe | 908 | 25 |

### ccp_db-crud_elasticsearch · 4 implementações · 2.152 bytes · 60 linhas

| # | Nome | Tipo | Bytes | Linhas |
|--:|---|---|--:|--:|
| 1 | FunctionResponseHandlerToMget | classe | 2.134 | 57 (acima) |
| 2 | ElasticSearchHttpStatus.NOT_FOUND | enum | 9 | 1 |
| 3 | ElasticSearchHttpStatus.CREATED | enum | 7 | 1 |
| 4 | ElasticSearchHttpStatus.OK | enum | 2 | 1 |

### ccp_db-query_elasticsearch · 2 implementações · 3.232 bytes · 81 linhas

| # | Nome | Tipo | Bytes | Linhas |
|--:|---|---|--:|--:|
| 1 | FunctionResponseHandlerToConsumeSearch | classe | 1.752 | 39 |
| 2 | FunctionSourceHandler | classe | 1.480 | 42 |

**Total geral:** 254 implementações · 557.881 bytes · 12.723 linhas.
