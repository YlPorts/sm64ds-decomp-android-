package org.ylports.sm64ds.nativeport;
import android.app.*;
import android.content.*;
import android.os.*;
import android.widget.*;
import java.io.*;
import java.util.Properties;

public final class LauncherActivity extends Activity {
    private TextView status;private Button importButton,startButton;private boolean importing;
    private File installed;
    @Override public void onCreate(Bundle state) {
        super.onCreate(state);
        LinearLayout box=new LinearLayout(this);box.setOrientation(1);box.setPadding(32,64,32,32);
        TextView title=new TextView(this);title.setText("Super Mario 64 DS");title.setTextSize(26);box.addView(title);
        TextView subtitle=new TextView(this);subtitle.setText("Port Android en desarrollo\nDos pantallas · controles táctiles\n\nImporta tu ROM europea, revisión 0 (.nds). Si tienes un .7z, descomprímelo primero. Esta APK no incluye el juego.");subtitle.setTextSize(16);box.addView(subtitle);
        importButton=new Button(this);importButton.setText("Seleccionar ROM");importButton.setOnClickListener(v->{
            Intent pick=new Intent(Intent.ACTION_OPEN_DOCUMENT).setType("*/*").addCategory(Intent.CATEGORY_OPENABLE);
            startActivityForResult(pick,7);
        });box.addView(importButton);
        startButton=new Button(this);startButton.setText("Iniciar motor");startButton.setOnClickListener(v->{
            if(installed!=null)startActivity(new Intent(this,GameActivity.class).putExtra("root",installed.getAbsolutePath()));
        });box.addView(startButton);
        Button report=new Button(this);report.setText("Ver registro de arranque");report.setOnClickListener(v->showLog());box.addView(report);
        status=new TextView(this);status.setTextSize(15);box.addView(status);setContentView(box);
        String root=getPreferences(0).getString("root",null);if(root!=null)installed=new File(root);refresh();
    }
    private void refresh(){
        boolean ready=installed!=null&&new File(installed,"READY").isFile();
        startButton.setEnabled(ready&&!importing);importButton.setEnabled(!importing);
        if(!importing)status.setText(ready?"Recursos preparados. Esta versión sigue en pruebas de arranque; la partida completa aún no está validada.":"Selecciona tu ROM para preparar los recursos.");
    }
    @Override protected void onActivityResult(int request,int result,Intent data) {
        super.onActivityResult(request,result,data);if(request!=7||result!=RESULT_OK||data==null||data.getData()==null)return;
        importing=true;refresh();final android.net.Uri uri=data.getData();
        new Thread(()->{
            try(InputStream rom=getContentResolver().openInputStream(uri);
                InputStream recipe=getAssets().open("romdata.recipe.tsv");
                InputStream manifest=getAssets().open("romdata.manifest");
                InputStream spec=getAssets().open("build.properties")) {
                Properties properties=new Properties();properties.load(spec);
                if(rom==null)throw new IOException("No se pudo abrir el archivo.");
                File root=RomImporter.install(rom,recipe,manifest,properties.getProperty("rom.sha256"),new File(getFilesDir(),"resources"),
                    message->runOnUiThread(()->status.setText(message)));
                runOnUiThread(()->{installed=root;getPreferences(0).edit().putString("root",root.getAbsolutePath()).apply();importing=false;refresh();});
            } catch(Exception error){runOnUiThread(()->{importing=false;refresh();status.setText(error.getMessage());});}
        },"ROM import").start();
    }
    private void showLog(){
        String text="Todavía no hay un registro de arranque.";
        if(installed!=null)try(FileInputStream in=new FileInputStream(new File(installed,"engine.log"))){
            ByteArrayOutputStream out=new ByteArrayOutputStream();byte[] bytes=new byte[4096];int n;
            while((n=in.read(bytes))!=-1&&out.size()<2*1024*1024)out.write(bytes,0,n);
            text=out.toString("UTF-8");if(text.length()>18000)text=text.substring(text.length()-18000);
        }catch(IOException ignored){}
        TextView view=new TextView(this);view.setText(text);view.setTextIsSelectable(true);view.setPadding(24,16,24,16);
        ScrollView scroll=new ScrollView(this);scroll.addView(view);new AlertDialog.Builder(this).setTitle("Registro del motor").setView(scroll).setPositiveButton("Cerrar",null).show();
    }
}
