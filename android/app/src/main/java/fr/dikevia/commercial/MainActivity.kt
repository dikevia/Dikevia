package fr.dikevia.commercial

import android.content.Intent
import android.net.Uri
import android.os.Bundle
import androidx.activity.ComponentActivity
import androidx.activity.compose.setContent
import androidx.compose.foundation.background
import androidx.compose.foundation.layout.*
import androidx.compose.foundation.horizontalScroll
import androidx.compose.foundation.rememberScrollState
import androidx.compose.foundation.lazy.LazyColumn
import androidx.compose.foundation.lazy.items
import androidx.compose.foundation.shape.RoundedCornerShape
import androidx.compose.material3.*
import androidx.compose.runtime.*
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.graphics.Color
import androidx.compose.ui.platform.LocalContext
import androidx.compose.ui.text.font.FontWeight
import androidx.compose.ui.unit.dp
import androidx.compose.ui.unit.sp
import kotlinx.coroutines.Dispatchers
import kotlinx.coroutines.withContext
import kotlinx.coroutines.launch
import net.openid.appauth.*
import okhttp3.MediaType.Companion.toMediaType
import okhttp3.OkHttpClient
import okhttp3.Request
import okhttp3.RequestBody.Companion.toRequestBody
import org.json.JSONArray
import org.json.JSONObject
import java.util.concurrent.TimeUnit

private val Emerald=Color(0xFF087F68)
private val Deep=Color(0xFF075B4D)
private val Dark=Color(0xFF063F37)
private val Gold=Color(0xFFF0D79F)
private val Ink=Color(0xFF142B25)
private val Muted=Color(0xFF637B71)
private val Canvas=Color(0xFFF3F8F5)

class MainActivity:ComponentActivity(){
    private var token by mutableStateOf<String?>(null)
    private var authError by mutableStateOf<String?>(null)
    private var authBusy by mutableStateOf(false)
    private var authService:AuthorizationService?=null
    companion object{
        const val API="https://dikevia-commercial-api-l2r8.onrender.com"
        const val ISSUER="https://dikevia-identity-l2r8.onrender.com/realms/cfdt"
        const val CLIENT_ID="dikevia-android"
        const val SCOPES="openid profile email"
        const val REDIRECT="fr.dikevia.commercial:/oauth2redirect"
        const val LOGIN_REQUEST=7301
    }
    override fun onCreate(savedInstanceState:Bundle?){
        super.onCreate(savedInstanceState);authService=AuthorizationService(this)
        setContent{MaterialTheme(colorScheme=lightColorScheme(primary=Deep,onPrimary=Gold,secondary=Emerald,background=Canvas,surface=Color.White,onSurface=Ink)){
            Root(token,authBusy,authError,::login){token=null;authError=null}
        }}
    }
    private fun login(){
        if(authBusy)return
        authBusy=true;authError=null
        AuthorizationServiceConfiguration.fetchFromIssuer(Uri.parse(ISSUER)){cfg,ex->
            if(cfg==null||ex!=null){runOnUiThread{authBusy=false;authError="Fournisseur de connexion indisponible."};return@fetchFromIssuer}
            val verifier=CodeVerifierUtil.generateRandomCodeVerifier()
            val req=AuthorizationRequest.Builder(cfg,CLIENT_ID,ResponseTypeValues.CODE,Uri.parse(REDIRECT))
                .setScope(SCOPES).setCodeVerifier(verifier).build()
            runOnUiThread{authBusy=false;startActivityForResult(authService!!.getAuthorizationRequestIntent(req),LOGIN_REQUEST)}
        }
    }
    @Deprecated("AppAuth activity result compatibility")
    override fun onActivityResult(requestCode:Int,resultCode:Int,data:Intent?){
        super.onActivityResult(requestCode,resultCode,data);if(requestCode!=LOGIN_REQUEST)return
        val intent=data?:Intent();val response=AuthorizationResponse.fromIntent(intent)
        val failure=AuthorizationException.fromIntent(intent)
        if(response==null){authError=if(failure!=null)"Connexion annulée ou refusée." else "Réponse OIDC invalide.";return}
        authBusy=true
        authService?.performTokenRequest(response.createTokenExchangeRequest()){result,error->
            runOnUiThread{authBusy=false
                if(error!=null||result?.accessToken.isNullOrBlank())authError="Échange du code OIDC impossible."
                else{token=result!!.accessToken;authError=null}
            }
        }
    }
    override fun onDestroy(){authService?.dispose();authService=null;super.onDestroy()}
}
private class Api{
    private val http=OkHttpClient.Builder().connectTimeout(20,TimeUnit.SECONDS).readTimeout(90,TimeUnit.SECONDS).callTimeout(100,TimeUnit.SECONDS).build()
    fun call(token:String,org:String?,path:String,method:String="GET",json:JSONObject?=null):String{
        val b=Request.Builder().url(MainActivity.API+path).header("Authorization","Bearer "+token).header("Accept","application/json")
        if(!org.isNullOrBlank())b.header("X-Organization-ID",org)
        if(method=="POST"||method=="PATCH")b.header("Content-Type","application/json").method(method,(json?:JSONObject()).toString().toRequestBody("application/json; charset=utf-8".toMediaType()))
        else b.method(method,null)
        http.newCall(b.build()).execute().use{r->
            val body=r.body?.string().orEmpty()
            if(!r.isSuccessful){
                val detail=runCatching{JSONObject(body).optString("detail")}.getOrNull()?.takeIf{it.isNotBlank()}
                val message=when(r.code){401->"Session expirée. Déconnectez-vous puis reconnectez-vous.";403->detail?: "Accès refusé pour ce compte ou ce rôle.";else->detail?:"Erreur serveur HTTP "+r.code}
                throw IllegalStateException(message)
            }
            return body
        }
    }
}
private data class Org(val id:String,val name:String,val role:String)
private data class Entry(val title:String,val detail:String)

@Composable private fun Root(token:String?,busy:Boolean,authError:String?,login:()->Unit,logout:()->Unit){
    val api=remember{Api()};var user by remember{mutableStateOf("")};var orgs by remember{mutableStateOf(emptyList<Org>())}
    var org by remember{mutableStateOf<Org?>(null)};var tab by remember{mutableStateOf("Accueil")}
    var resumeConversationId by remember{mutableStateOf<String?>(null)}
    var loading by remember{mutableStateOf(false)};var error by remember{mutableStateOf<String?>(null)}
    LaunchedEffect(token){
        if(token!=null){loading=true;error=null
            try{
                val me=withContext(Dispatchers.IO){JSONObject(api.call(token,null,"/api/v1/auth/me"))}
                user=me.optString("display_name").ifBlank{me.optString("email")}
                val data=withContext(Dispatchers.IO){JSONArray(api.call(token,null,"/api/v1/organizations"))}
                orgs=(0 until data.length()).map{val o=data.getJSONObject(it);Org(o.getString("id"),o.optString("display_name"),o.optString("role"))}
                org=orgs.firstOrNull();if(org==null)error="Aucune organisation active n'est associée à ce compte."
            }catch(e:Exception){error=e.message?:"Connexion au service impossible."}finally{loading=false}
        }else{user="";orgs=emptyList();org=null}
    }
    Surface(Modifier.fillMaxSize(),color=Canvas){
        if(token==null)LoginPage(busy,authError,login)
        else Column(Modifier.fillMaxSize()){
            Header(user,orgs,org){org=it}
            if(loading)LinearProgressIndicator(Modifier.fillMaxWidth(),color=Emerald)
            error?.let{ErrorBox(it)}
            org?.let{current->Box(Modifier.weight(1f).fillMaxWidth()){
                when(tab){
                    "Accueil"->Home(user,current){tab=it}
                    "Assistant"->Assistant(token,current,api,resumeConversationId){resumeConversationId=null}
                    "Historique"->HistoryPage(token,current,api){id->resumeConversationId=id;tab="Assistant"}
                    "Documents"->Listing("Documents",token,current,api,"/api/v1/documents"){Entry(it.optString("title"),listOf(it.optString("document_type"),it.optString("validation_status"),it.optString("collectivity_name")).filter{s->s.isNotBlank()}.joinToString(" · "))}
                    "Collectivités"->Listing("Collectivités",token,current,api,"/api/v1/collectivities"){Entry(it.optString("name"),it.optString("code"))}
                    "Membres"->Listing("Membres",token,current,api,"/api/v1/organizations/me/members"){Entry(it.optString("display_name").ifBlank{it.optString("email")},it.optString("role")+" · "+it.optString("status"))}
                    else->Profile(user,current,logout)
                }
            }}
            Nav(tab){tab=it}
        }
    }
}
@Composable private fun LoginPage(busy:Boolean,error:String?,login:()->Unit){
    Column(Modifier.fillMaxSize().padding(25.dp),verticalArrangement=Arrangement.Center,horizontalAlignment=Alignment.CenterHorizontally){
        Text("Dikévia",fontSize=35.sp,fontWeight=FontWeight.ExtraBold,color=Dark)
        Text("Votre espace d'assistance juridique",color=Muted);Spacer(Modifier.height(25.dp))
        Card(shape=RoundedCornerShape(20.dp),colors=CardDefaults.cardColors(containerColor=Color.White)){
            Column(Modifier.padding(22.dp),horizontalAlignment=Alignment.CenterHorizontally){
                Text("Accéder à votre espace",fontSize=21.sp,fontWeight=FontWeight.Bold)
                Text("La connexion est assurée par le fournisseur d'identité de votre organisation.",color=Muted,fontSize=13.sp,modifier=Modifier.padding(top=10.dp))
                Button(onClick=login,enabled=!busy,modifier=Modifier.fillMaxWidth().padding(top=18.dp).height(50.dp),colors=ButtonDefaults.buttonColors(containerColor=Deep,contentColor=Gold)){Text(if(busy)"Connexion…" else "Se connecter")}
                error?.let{Text(it,color=Color(0xFF9B3030),fontSize=12.sp,modifier=Modifier.padding(top=10.dp))}
                Text("Aucun mot de passe n'est demandé ni stocké par Dikévia.",color=Muted,fontSize=11.sp,modifier=Modifier.padding(top=12.dp))
            }
        }
    }
}
@Composable private fun Header(user:String,orgs:List<Org>,org:Org?,select:(Org)->Unit){
    Column(Modifier.fillMaxWidth().background(Dark).padding(15.dp)){Row(verticalAlignment=Alignment.CenterVertically){
        Column(Modifier.weight(1f)){Text("Dikévia",color=Color.White,fontSize=20.sp,fontWeight=FontWeight.Bold);Text(user,color=Color(0xFFD4E7DF),fontSize=12.sp)}
        if(orgs.size>1){var expanded by remember{mutableStateOf(false)};Box{
            TextButton(onClick={expanded=true}){Text(org?.name?:"Organisation",color=Gold)}
            DropdownMenu(expanded,{expanded=false}){orgs.forEach{o->DropdownMenuItem(text={Text(o.name)},onClick={select(o);expanded=false})}}
        }}
    }}
}
@Composable private fun Home(user:String,org:Org,navigate:(String)->Unit){
    LazyColumn(Modifier.fillMaxSize().padding(17.dp),verticalArrangement=Arrangement.spacedBy(12.dp)){
        item{Text("Bonjour "+user.substringBefore(" ").ifBlank{"et bienvenue"},fontSize=24.sp,fontWeight=FontWeight.Bold,color=Ink)}
        item{Card(colors=CardDefaults.cardColors(containerColor=Color.White)){Column(Modifier.padding(16.dp)){Text(org.name,color=Dark,fontWeight=FontWeight.Bold,fontSize=17.sp);Text("Rôle : "+org.role,color=Muted,fontSize=12.sp)}}}
        item{Action("Assistant juridique","Posez une question et consultez les sources.","Ouvrir l'assistant"){navigate("Assistant")}}
        item{Action("Mes documents","Retrouvez les documents de votre collectivité.","Consulter"){navigate("Documents")}}
        item{Action("Historique","Reprenez vos précédentes conversations.","Voir l'historique"){navigate("Historique")}}
    }
}
@Composable private fun Action(title:String,desc:String,button:String,click:()->Unit){
    Card(colors=CardDefaults.cardColors(containerColor=Color.White),shape=RoundedCornerShape(15.dp)){Column(Modifier.padding(16.dp)){
        Text(title,fontWeight=FontWeight.Bold,color=Ink,fontSize=17.sp);Text(desc,color=Muted,fontSize=13.sp)
        Button(onClick=click,modifier=Modifier.padding(top=9.dp),colors=ButtonDefaults.buttonColors(containerColor=Deep,contentColor=Gold)){Text(button)}
    }}
}
@Composable private fun Assistant(token:String,org:Org,api:Api,initialConversationId:String?,onNewConversation:()->Unit){
    val context=LocalContext.current
    var q by remember{mutableStateOf("")};var employer by remember{mutableStateOf("NATIONAL")};var answer by remember{mutableStateOf<JSONObject?>(null)}
    var previousMessages by remember(org.id,initialConversationId){mutableStateOf(emptyList<JSONObject>())}
    var conversationId by remember(org.id,initialConversationId){mutableStateOf(initialConversationId)}
    var factsStart by remember{mutableStateOf("")};var factsEnd by remember{mutableStateOf("")};var ongoing by remember{mutableStateOf(false)}
    var collectivityId by remember{mutableStateOf<String?>(null)};var collectivities by remember{mutableStateOf(emptyList<JSONObject>())}
    var collectivityExpanded by remember{mutableStateOf(false)}
    var waiting by remember{mutableStateOf(false)};var error by remember{mutableStateOf<String?>(null)};val scope=rememberCoroutineScope()
    LaunchedEffect(org.id,initialConversationId){
        answer=null;error=null;previousMessages=emptyList();q=""
        if(initialConversationId!=null)try{
            val data=withContext(Dispatchers.IO){JSONArray(api.call(token,org.id,"/api/v1/chat/conversations/"+initialConversationId+"/messages"))}
            previousMessages=(0 until data.length()).map{data.getJSONObject(it)}
        }catch(e:Exception){error=e.message?:"Impossible de charger cette conversation."}
    }
    LaunchedEffect(org.id){
        try{val data=withContext(Dispatchers.IO){JSONArray(api.call(token,org.id,"/api/v1/collectivities"))}
            collectivities=(0 until data.length()).map{data.getJSONObject(it)}
        }catch(_:Exception){collectivities=emptyList()}
    }
    Column(Modifier.fillMaxSize().padding(13.dp)){
        Text(if(initialConversationId==null)"Assistant juridique" else "Conversation reprise",fontSize=23.sp,fontWeight=FontWeight.Bold,color=Ink)
        Text("Le statut de vérification et les sources accompagnent chaque réponse.",color=Muted,fontSize=12.sp);Spacer(Modifier.height(9.dp))
        LazyColumn(Modifier.weight(1f).fillMaxWidth()){
            items(previousMessages){m->
                val isUser=m.optString("role")=="user"
                Card(Modifier.fillMaxWidth().padding(vertical=3.dp),colors=CardDefaults.cardColors(containerColor=if(isUser)Color(0xFFE2F5EE) else Color.White)){
                    Column(Modifier.padding(11.dp)){
                        Text(if(isUser)"Vous" else "Dikévia",fontSize=10.sp,fontWeight=FontWeight.Bold,color=if(isUser)Deep else Emerald)
                        Text(m.optString("content"),fontSize=13.sp,color=Ink)
                    }
                }
            }
            item{answer?.let{r->Card(colors=CardDefaults.cardColors(containerColor=Color.White)){Column(Modifier.padding(14.dp)){
                val status=r.optString("verification_status","NON_VERIFIE")
                Text("Vérification : "+status,color=if(status=="VERIFIE")Emerald else Color(0xFF946A19),fontWeight=FontWeight.Bold)
                Text(r.optString("answer"),color=Ink,modifier=Modifier.padding(top=8.dp))
                r.optString("clarification_question").takeIf{it.isNotBlank()}?.let{Text("Précision nécessaire : "+it,color=Muted,modifier=Modifier.padding(top=8.dp))}
                val missing=r.optJSONArray("missing_information")?:JSONArray()
                if(missing.length()>0){
                    Text("Informations manquantes",fontWeight=FontWeight.Bold,color=Dark,modifier=Modifier.padding(top=10.dp))
                    for(i in 0 until missing.length())Text("• "+missing.optString(i),fontSize=12.sp,color=Muted)
                }
                val sources=r.optJSONArray("sources")?:JSONArray()
                Text("Sources documentaires ("+sources.length()+")",fontWeight=FontWeight.Bold,color=Dark,modifier=Modifier.padding(top=10.dp))
                for(i in 0 until sources.length()){val s=sources.optJSONObject(i)?:continue
                    Text("• "+s.optString("title","Source juridique"),fontSize=12.sp,color=Ink)
                    s.optString("excerpt").takeIf{it.isNotBlank()}?.let{Text(it,fontSize=11.sp,color=Muted)}
                    val official=s.optString("official_url").ifBlank{s.optString("source_url")}
                    val host=runCatching{Uri.parse(official).host}.getOrNull()
                    if(official.startsWith("https://") && (host=="legifrance.gouv.fr" || host=="www.legifrance.gouv.fr")){
                        TextButton(onClick={context.startActivity(Intent(Intent.ACTION_VIEW,Uri.parse(official)))}){Text("Consulter la source officielle",color=Emerald,fontSize=11.sp)}
                    }
                }
                r.optString("disclaimer").takeIf{it.isNotBlank()}?.let{Text(it,fontSize=11.sp,color=Muted,modifier=Modifier.padding(top=8.dp))}
                Text("Une réponse assistée ne remplace pas la vérification du texte applicable ni l'avis du service juridique.",fontSize=10.sp,color=Muted,modifier=Modifier.padding(top=6.dp))
            }}}?:Text("Posez votre question. Dikévia indiquera si la réponse est vérifiée ou si des précisions sont nécessaires.",color=Muted)}
        }
        error?.let{ErrorBox(it)}
        OutlinedTextField(q,{if(it.length<=5000)q=it},modifier=Modifier.fillMaxWidth(),label={Text("Votre question (8 à 5 000 caractères)")},minLines=3)
        Row(horizontalArrangement=Arrangement.spacedBy(8.dp)){
            OutlinedTextField(factsStart,{factsStart=it},modifier=Modifier.weight(1f),label={Text("Début (AAAA-MM-JJ)")},singleLine=true)
            OutlinedTextField(factsEnd,{factsEnd=it},modifier=Modifier.weight(1f),label={Text("Fin (AAAA-MM-JJ)")},singleLine=true,enabled=!ongoing)
        }
        Row(verticalAlignment=Alignment.CenterVertically){
            Checkbox(checked=ongoing,onCheckedChange={ongoing=it;if(it)factsEnd=""})
            Text("Situation toujours en cours",fontSize=12.sp,color=Muted)
        }
        if(collectivities.isNotEmpty()){
            Box{OutlinedButton(onClick={collectivityExpanded=true}){
                val chosen=collectivities.firstOrNull{it.optString("id")==collectivityId}
                Text(chosen?.optString("name")?:"Choisir une collectivité (facultatif)")
            }
                DropdownMenu(collectivityExpanded,{collectivityExpanded=false}){
                    DropdownMenuItem(text={Text("Aucune collectivité précise")},onClick={collectivityId=null;collectivityExpanded=false})
                    collectivities.forEach{c->DropdownMenuItem(text={Text(c.optString("name"))},onClick={collectivityId=c.optString("id");collectivityExpanded=false})}
                }
            }
        }
        var expanded by remember{mutableStateOf(false)}
        Box{OutlinedButton(onClick={expanded=true}){Text(when(employer){"VILLE_SAINT_ETIENNE"->"Ville de Saint-Étienne";"SAINT_ETIENNE_METROPOLE"->"Saint-Étienne Métropole";else->"National / autre collectivité"})}
            DropdownMenu(expanded,{expanded=false}){
                DropdownMenuItem(text={Text("National / autre collectivité")},onClick={employer="NATIONAL";expanded=false})
                DropdownMenuItem(text={Text("Ville de Saint-Étienne")},onClick={employer="VILLE_SAINT_ETIENNE";expanded=false})
                DropdownMenuItem(text={Text("Saint-Étienne Métropole")},onClick={employer="SAINT_ETIENNE_METROPOLE";expanded=false})
            }}
        Row(horizontalArrangement=Arrangement.spacedBy(8.dp),verticalAlignment=Alignment.CenterVertically){
            Button(onClick={val question=q.trim();if(question.length>=8&&!waiting){waiting=true;error=null;scope.launch{
            try{
                val payload=JSONObject().put("employer",employer).put("question",question).put("situation_ongoing",ongoing)
                if(factsStart.isNotBlank())payload.put("facts_start_date",factsStart.trim())
                if(factsEnd.isNotBlank()&&!ongoing)payload.put("facts_end_date",factsEnd.trim())
                collectivityId?.let{payload.put("collectivity_id",it)}
                conversationId?.let{payload.put("conversation_id",it)}
                val prior=answer
                if(prior!=null)previousMessages=previousMessages+JSONObject().put("role","assistant").put("content",prior.optString("answer"))
                previousMessages=previousMessages+JSONObject().put("role","user").put("content",question)
                val response=withContext(Dispatchers.IO){JSONObject(api.call(token,org.id,"/api/v1/chat/ask","POST",payload))}
                answer=response
                conversationId=response.optString("conversation_id").takeIf{it.isNotBlank()&&it!="null"}
                q=""
            }
            catch(e:Exception){error=e.message?:"Demande impossible."}finally{waiting=false}
        }}},enabled=!waiting&&q.trim().length>=8,modifier=Modifier.weight(1f).height(48.dp),colors=ButtonDefaults.buttonColors(containerColor=Deep,contentColor=Gold)){Text(if(waiting)"Analyse en cours…" else "Envoyer")}
            OutlinedButton(onClick={conversationId=null;answer=null;previousMessages=emptyList();q="";factsStart="";factsEnd="";ongoing=false;collectivityId=null;onNewConversation()},enabled=!waiting){Text("Nouveau")}
        }
    }
}

@Composable private fun HistoryPage(token:String,org:Org,api:Api,onContinue:(String)->Unit){
    val context=LocalContext.current
    var conversations by remember{mutableStateOf(emptyList<JSONObject>())}
    var selected by remember{mutableStateOf<String?>(null)}
    var messages by remember{mutableStateOf(emptyList<JSONObject>())}
    var loading by remember{mutableStateOf(true)}
    var error by remember{mutableStateOf<String?>(null)}
    LaunchedEffect(token,org.id){
        loading=true;error=null
        try{
            val data=withContext(Dispatchers.IO){JSONArray(api.call(token,org.id,"/api/v1/chat/conversations"))}
            conversations=(0 until data.length()).map{data.getJSONObject(it)}
        }catch(e:Exception){error=e.message?:"Chargement de l'historique impossible."}
        finally{loading=false}
    }
    LaunchedEffect(selected){
        val id=selected
        if(id!=null){
            loading=true;error=null
            try{
                val data=withContext(Dispatchers.IO){JSONArray(api.call(token,org.id,"/api/v1/chat/conversations/"+id+"/messages"))}
                messages=(0 until data.length()).map{data.getJSONObject(it)}
            }catch(e:Exception){error=e.message?:"Impossible de rouvrir cette conversation."}
            finally{loading=false}
        }else{messages=emptyList()}
    }
    Column(Modifier.fillMaxSize().padding(16.dp)){
        Row(verticalAlignment=Alignment.CenterVertically){
            Text(if(selected==null)"Historique" else "Conversation",fontSize=23.sp,fontWeight=FontWeight.Bold,color=Ink,modifier=Modifier.weight(1f))
            if(selected!=null)TextButton(onClick={selected=null}){Text("Retour",color=Deep)}
        }
        if(loading)LinearProgressIndicator(Modifier.fillMaxWidth(),color=Emerald)
        error?.let{ErrorBox(it)}
        if(selected==null){
            if(!loading&&conversations.isEmpty()&&error==null)Text("Aucune conversation enregistrée.",color=Muted)
            LazyColumn(verticalArrangement=Arrangement.spacedBy(8.dp)){
                items(conversations){c->
                    Card(colors=CardDefaults.cardColors(containerColor=Color.White)){
                        Column(Modifier.fillMaxWidth().padding(13.dp)){
                            Text(c.optString("title","Conversation"),fontWeight=FontWeight.SemiBold,color=Ink)
                            Text(c.optInt("message_count").toString()+" message(s)",color=Muted,fontSize=11.sp)
                            Row(horizontalArrangement=Arrangement.spacedBy(6.dp)){
                                TextButton(onClick={selected=c.optString("id")}){Text("Ouvrir",color=Deep)}
                                TextButton(onClick={onContinue(c.optString("id"))}){Text("Continuer",color=Emerald)}
                            }
                        }
                    }
                }
            }
        }else{
            LazyColumn(verticalArrangement=Arrangement.spacedBy(8.dp)){
                items(messages){m->
                    val isUser=m.optString("role")=="user"
                    Card(colors=CardDefaults.cardColors(containerColor=if(isUser)Color(0xFFE2F5EE) else Color.White)){
                        Column(Modifier.fillMaxWidth().padding(13.dp)){
                            Text(if(isUser)"Vous" else "Dikévia",fontWeight=FontWeight.Bold,color=if(isUser)Deep else Emerald,fontSize=11.sp)
                            Text(m.optString("content"),color=Ink,fontSize=13.sp)
                            if(!isUser){
                                val metadata=m.optJSONObject("metadata")?:JSONObject()
                                metadata.optString("verification_status").takeIf{it.isNotBlank()}?.let{
                                    Text("Vérification : "+it,fontSize=10.sp,fontWeight=FontWeight.Bold,color=if(it=="VERIFIE")Emerald else Color(0xFF946A19),modifier=Modifier.padding(top=6.dp))
                                }
                                val sources=metadata.optJSONArray("sources")?:JSONArray()
                                for(i in 0 until sources.length()){
                                    val source=sources.optJSONObject(i)?:continue
                                    Text("• "+source.optString("title","Source juridique"),fontSize=11.sp,color=Muted,modifier=Modifier.padding(top=4.dp))
                                    source.optString("excerpt").takeIf{it.isNotBlank()}?.let{Text(it,fontSize=10.sp,color=Muted)}
                                    val url=source.optString("official_url").ifBlank{source.optString("source_url")}
                                    val host=runCatching{Uri.parse(url).host}.getOrNull()
                                    if(url.startsWith("https://")&&(host=="legifrance.gouv.fr"||host=="www.legifrance.gouv.fr")){
                                        TextButton(onClick={context.startActivity(Intent(Intent.ACTION_VIEW,Uri.parse(url)))}){Text("Consulter Légifrance",fontSize=10.sp,color=Emerald)}
                                    }
                                }
                                metadata.optString("disclaimer").takeIf{it.isNotBlank()}?.let{Text(it,fontSize=10.sp,color=Muted)}
                            }
                        }
                    }
                }
            }
        }
    }
}

@Composable private fun Listing(title:String,token:String,org:Org,api:Api,path:String,convert:(JSONObject)->Entry){
    var rows by remember{mutableStateOf(emptyList<Entry>())};var loading by remember{mutableStateOf(true)};var error by remember{mutableStateOf<String?>(null)}
    LaunchedEffect(path,org.id){loading=true;try{val data=withContext(Dispatchers.IO){JSONArray(api.call(token,org.id,path))};rows=(0 until data.length()).map{convert(data.getJSONObject(it))}}
        catch(e:Exception){error=e.message?:"Chargement impossible."}finally{loading=false}}
    Column(Modifier.fillMaxSize().padding(17.dp)){Text(title,fontSize=23.sp,fontWeight=FontWeight.Bold,color=Ink)
        if(loading)LinearProgressIndicator(Modifier.fillMaxWidth().padding(top=10.dp),color=Emerald)
        error?.let{ErrorBox(it)}
        if(!loading&&error==null&&rows.isEmpty())Text("Aucun élément pour le moment.",color=Muted,modifier=Modifier.padding(top=12.dp))
        LazyColumn(Modifier.padding(top=10.dp),verticalArrangement=Arrangement.spacedBy(8.dp)){items(rows){row->Card(colors=CardDefaults.cardColors(containerColor=Color.White)){
            Column(Modifier.fillMaxWidth().padding(14.dp)){Text(row.title,color=Ink,fontWeight=FontWeight.SemiBold);if(row.detail.isNotBlank())Text(row.detail,color=Muted,fontSize=12.sp)}
        }}}
    }
}
@Composable private fun Profile(user:String,org:Org,logout:()->Unit){
    Column(Modifier.fillMaxSize().padding(20.dp),verticalArrangement=Arrangement.spacedBy(12.dp)){
        Text("Mon profil",fontSize=24.sp,fontWeight=FontWeight.Bold,color=Ink)
        Card(colors=CardDefaults.cardColors(containerColor=Color.White)){Column(Modifier.padding(16.dp)){Text(user,fontWeight=FontWeight.Bold);Text(org.name,color=Muted);Text("Rôle : "+org.role,color=Muted,fontSize=12.sp)}}
        Button(onClick=logout,colors=ButtonDefaults.buttonColors(containerColor=Color(0xFF9B3030))){Text("Se déconnecter",color=Color.White)}
    }
}
@Composable private fun Nav(selected:String,choose:(String)->Unit){
    val tabs=listOf("Accueil","Assistant","Historique","Documents","Collectivités","Membres","Profil")
    Surface(color=Color.White,shadowElevation=5.dp){Row(Modifier.fillMaxWidth().horizontalScroll(rememberScrollState()).navigationBarsPadding(),verticalAlignment=Alignment.CenterVertically){
        tabs.forEach{tab->TextButton(onClick={choose(tab)}){Text(tab,color=if(selected==tab)Deep else Muted,fontWeight=if(selected==tab)FontWeight.Bold else FontWeight.Normal,fontSize=11.sp)}}
    }}
}
@Composable private fun ErrorBox(message:String){
    Card(colors=CardDefaults.cardColors(containerColor=Color(0xFFFFF0EF)),modifier=Modifier.fillMaxWidth().padding(8.dp)){
        Text(message,color=Color(0xFF8B2929),fontSize=12.sp,modifier=Modifier.padding(12.dp))
    }
}
