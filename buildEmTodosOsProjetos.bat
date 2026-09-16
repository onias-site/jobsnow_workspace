@echo off
setlocal
set "BASE=%~dp0"

echo ######################
echo Buildando o projeto: ccp_commons_jobsnow
pushd "%BASE%ccp_commons_jobsnow"
call mvn clean install
popd

echo ######################
echo Buildando o projeto: ccp_json_gson
pushd "%BASE%ccp_json_gson"
call mvn clean install
popd

echo ######################
echo Buildando o projeto: ccp_cache_gcp-memcache
pushd "%BASE%ccp_cache_gcp-memcache"
call mvn clean install
popd

echo ######################
echo Buildando o projeto: ccp_cron-tasks_jobsnow
pushd "%BASE%ccp_cron-tasks_jobsnow"
call mvn clean install
popd

echo ######################
echo Buildando o projeto: ccp_db-bulk_elasticsearch
pushd "%BASE%ccp_db-bulk_elasticsearch"
call mvn clean install
popd

echo ######################
echo Buildando o projeto: ccp_db-crud_elasticsearch
pushd "%BASE%ccp_db-crud_elasticsearch"
call mvn clean install
popd

echo ######################
echo Buildando o projeto: ccp_db-utils_elasticsearch
pushd "%BASE%ccp_db-utils_elasticsearch"
call mvn clean install
popd

echo ######################
echo Buildando o projeto: ccp_email_sendgrid
pushd "%BASE%ccp_email_sendgrid"
call mvn clean install
popd

echo ######################
echo Buildando o projeto: ccp_file-bucket_gcp
pushd "%BASE%ccp_file-bucket_gcp"
call mvn clean install
popd

echo ######################
echo Buildando o projeto: ccp_http_apache-mime
pushd "%BASE%ccp_http_apache-mime"
call mvn clean install
popd

echo ######################
echo Buildando o projeto: ccp_instant-messenger_telegram
pushd "%BASE%ccp_instant-messenger_telegram"
call mvn clean install
popd

echo ######################
echo Buildando o projeto: ccp_main-authentication_gcp-oauth
pushd "%BASE%ccp_main-authentication_gcp-oauth"
call mvn clean install
popd

echo ######################
echo Buildando o projeto: ccp_mensageria-consumer_gcp-pubsub-pull_dependency-chooser
pushd "%BASE%ccp_mensageria-consumer_gcp-pubsub-pull_dependency-chooser"
call mvn clean install
popd

echo ######################
echo Buildando o projeto: ccp_mensageria-sender_gcp-pubsub
pushd "%BASE%ccp_mensageria-sender_gcp-pubsub"
call mvn clean install
popd

echo ######################
echo Buildando o projeto: ccp_password_mindrot
pushd "%BASE%ccp_password_mindrot"
call mvn clean install
popd

echo ######################
echo Buildando o projeto: ccp_text-extractor_apache-tika
pushd "%BASE%ccp_text-extractor_apache-tika"
call mvn clean install
popd

echo ######################
echo Buildando o projeto: jn_business_jobsnow
pushd "%BASE%jn_business_jobsnow"
call mvn clean install
popd

echo ######################
echo Buildando o projeto: ccp_rest-api-handler-exception_spring
pushd "%BASE%ccp_rest-api-handler-exception_spring"
call mvn clean install
popd

echo ######################
echo Buildando o projeto: ccp_db-query_elasticsearch
pushd "%BASE%ccp_db-query_elasticsearch"
call mvn clean install
popd

echo ######################
echo Buildando o projeto: vis_business_jobsnow
pushd "%BASE%vis_business_jobsnow"
call mvn clean install
popd

echo ######################
echo Buildando o projeto: jb_business_jobsnow
pushd "%BASE%jb_business_jobsnow"
call mvn clean install
popd

echo ######################
echo Buildando o projeto: jn_mensageria-consumer_gcp-pubsub-push-spring_dependency
pushd "%BASE%jn_mensageria-consumer_gcp-pubsub-push-spring_dependency"
call mvn clean install
popd

echo ######################
echo Buildando o projeto: ccp_mocking_jobsnow
pushd "%BASE%ccp_mocking_jobsnow"
call mvn clean install
popd

echo ######################
echo Buildando o projeto: jn_rest-api_spring_jobsnow_dependency-chooser
pushd "%BASE%jn_rest-api_spring_jobsnow_dependency-chooser"
call mvn clean install
popd

echo ######################
echo Buildando o projeto: vis_rest-api_spring_jobsnow_dependency-chooser
pushd "%BASE%vis_rest-api_spring_jobsnow_dependency-chooser"
call mvn clean install
popd

echo ######################
echo Buildando o projeto: ccp_rest-api-tests_jobsnow
pushd "%BASE%ccp_rest-api-tests_jobsnow"
call mvn clean install
popd

echo ######################
echo Terminou de buildar todos os projetos, seja feliz :)
endlocal
pause